"""The permission gate every tool call must pass through before executing.

This is deliberately the single choke point described in
docs/ARCHITECTURE.md — don't let tools bypass it.
"""

from __future__ import annotations

import datetime as _dt
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from tools.base import Tool
from tools.scoping import is_within_project_roots

ACTIVITY_LOG_PATH = Path(__file__).parent.parent / "db" / "activity_log.jsonl"

# Tier 1 reads are auto-approved. Everything else defaults to requiring
# confirmation until the project/dir/command has been explicitly trusted.
# TODO(fable-5): replace this with a real per-project trust store instead
# of a single global flag.
AUTO_APPROVE_TIER_1_READS = True


@dataclass
class ActivityLog:
    path: Path = ACTIVITY_LOG_PATH

    def record(self, tool_name: str, tier: int, args: dict, approved: bool, result: str) -> None:
        entry = {
            "timestamp": _dt.datetime.now().isoformat(),
            "tool": tool_name,
            "tier": tier,
            "args": args,
            "approved": approved,
            "result_preview": (result or "")[:500],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


class PermissionDenied(Exception):
    pass


# --- Tier 2 policy: which terminal commands skip confirmation -------------
# HANDOFF.md: "An allowlist (e.g. ls, git status, cat) runs without asking.
# Anything not on the allowlist shows the literal command about to run and
# requires explicit user confirmation." Read-only-ish only — nothing that
# writes, moves, installs, or kills belongs here.

READ_ONLY_COMMANDS = {
    "cat", "date", "echo", "file", "find", "grep", "head", "ls",
    "pwd", "stat", "tail", "tree", "wc", "which",
}

READ_ONLY_GIT_SUBCOMMANDS = {
    "blame", "branch", "describe", "diff", "log", "ls-files",
    "remote", "rev-parse", "shortlog", "show", "status",
}

# Flags that let an otherwise read-only command write or execute.
FORBIDDEN_FLAGS = {
    "find": {"-delete", "-exec", "-execdir", "-ok", "-okdir",
             "-fls", "-fprint", "-fprint0", "-fprintf"},
}


def _path_arg_is_in_scope(arg: str) -> bool:
    """Path-looking args must stay inside the registered project roots, so
    `cat /etc/passwd` can't inherit `cat`'s auto-approval."""
    if not (arg.startswith(("/", "~")) or ".." in arg):
        return True
    return is_within_project_roots(Path(arg).expanduser().resolve())


def is_command_allowlisted(command: str) -> bool:
    """True if `command` is read-only enough to run without confirmation.

    Deliberately conservative: anything unparseable, unrecognised, or aimed
    outside the project roots returns False — which means "ask the user",
    never "block".
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if not argv:
        return False

    program, args = argv[0], argv[1:]
    if program == "git":
        # `git -C <dir> ...` would escape the sandboxed cwd, so only a bare
        # read-only subcommand in first position qualifies.
        if not args or args[0] not in READ_ONLY_GIT_SUBCOMMANDS:
            return False
        args = args[1:]
    elif program in READ_ONLY_COMMANDS:
        if any(a in FORBIDDEN_FLAGS.get(program, set()) for a in args):
            return False
    else:
        return False

    return all(_path_arg_is_in_scope(a) for a in args)


def request_confirmation(tool: Tool, args: dict) -> bool:
    """Ask the user to approve a tool call.

    TODO(fable-5): this is a CLI stand-in. Replace with a real UI prompt
    surfaced through the frontend (see HANDOFF.md open question on
    confirmation UI pattern). Keep the function signature stable so the
    orchestrator doesn't need to change when this gets a real UI.
    """
    print(f"\n[TARS] Wants to run tier {tool.tier} tool: {tool.name}")
    print(f"        args: {json.dumps(args)}")
    answer = input("        Approve? [y/N] ").strip().lower()
    return answer == "y"


def gate(tool: Tool, args: dict, log: ActivityLog) -> bool:
    """Return True if the tool call is allowed to proceed."""
    if tool.tier == 1 and AUTO_APPROVE_TIER_1_READS and tool.name.startswith("read_"):
        return True
    # run_command is named explicitly rather than self-declaring: base.py is
    # clear that the ask-or-not decision belongs to this module, and for
    # Tier 2 that decision depends on the command string, not just the tool.
    if tool.name == "run_command" and is_command_allowlisted(str(args.get("command", ""))):
        return True
    approved = request_confirmation(tool, args)
    if not approved:
        log.record(tool.name, tool.tier, args, approved=False, result="denied by user")
    return approved
