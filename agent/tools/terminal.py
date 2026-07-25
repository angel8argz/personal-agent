"""Tier 2 tools: terminal commands.

Follows tools/file_tools.py's shape — plain functions plus a `Tool`
declaration at the bottom, tier-tagged honestly.

This module only *executes*. Whether a given command runs straight through or
has to be confirmed by the user first is permissions.py's call (see
READ_ONLY_COMMANDS / is_command_allowlisted there), per base.py's rule that a
tool never decides its own confirmation policy.

Two hard invariants here:
  - No shell. Commands are argv lists via shlex, never `shell=True`.
  - The working directory must resolve inside a registered project root.
"""

from __future__ import annotations

import shlex
import subprocess

from tools.base import Tool
from tools.scoping import resolve_within_project_roots

TIMEOUT_SECONDS = 20
MAX_OUTPUT_CHARS = 20_000  # same context-safety cap as file_tools.read_file

# Without a shell these are inert literal argv entries, so a piped or chained
# command would silently do something other than what the model intended.
# Reject with an explanation instead of running the wrong thing. Checked
# token-wise (not as substrings) so quoted regexes like 'foo$' still work.
OPERATOR_TOKENS = {"|", "||", "&", "&&", ";", ";;", ">", ">>", "<", "<<"}


def _reject_shell_operators(argv: list[str]) -> None:
    for token in argv:
        if token in OPERATOR_TOKENS or token.endswith(";"):
            raise ValueError(
                f"'{token}' needs a shell, and TARS runs commands without one. "
                "Send one command per call — no pipes, redirects, or chaining."
            )


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... (truncated at {MAX_OUTPUT_CHARS} chars)"


def _format_result(proc: subprocess.CompletedProcess) -> str:
    parts = [f"exit code: {proc.returncode}"]
    for label, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        text = (stream or "").rstrip()
        if text:
            parts.append(f"--- {label} ---\n{_cap(text)}")
    if len(parts) == 1:
        parts.append("(no output)")
    return "\n".join(parts)


def run_command(command: str, cwd: str) -> str:
    """Run `command` (no shell) with `cwd` as the working directory."""
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty command")
    _reject_shell_operators(argv)

    working_dir = resolve_within_project_roots(cwd)
    if not working_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {working_dir}")

    try:
        proc = subprocess.run(  # noqa: S603 - argv list, never shell=True
            argv,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise FileNotFoundError(f"Command not found: {argv[0]}") from None
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"'{command}' exceeded {TIMEOUT_SECONDS}s and was killed"
        ) from None

    return _format_result(proc)


TOOLS = [
    Tool(
        name="run_command",
        description=(
            "Run a single terminal command inside a registered project directory. "
            "No shell is used, so pipes, redirects, globs and chaining are "
            "unavailable — send one plain command per call. Read-only commands "
            "run immediately; anything else is shown to the user for approval "
            "first."
        ),
        tier=2,
        parameters_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command and its arguments, e.g. 'git status'",
                },
                "cwd": {
                    "type": "string",
                    "description": "Directory to run in; must be inside a registered project",
                },
            },
            "required": ["command", "cwd"],
        },
        fn=run_command,
    ),
]
