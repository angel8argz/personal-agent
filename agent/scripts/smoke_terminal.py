"""Non-interactive smoke test for the Tier 2 terminal tool and its
confirmation policy.

Run:
    agent/.venv/bin/python agent/scripts/smoke_terminal.py

Exits 0 with "SMOKE TERMINAL: OK" on success, non-zero with a message on
failure. Nothing here needs Ollama running.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))


def check_execution(terminal, project_dir: str) -> None:
    (Path(project_dir) / "sentinel.txt").write_text("hi")

    out = terminal.run_command("ls", cwd=project_dir)
    assert "exit code: 0" in out, f"expected a clean exit from ls: {out!r}"
    assert "sentinel.txt" in out, f"ls did not list the seeded file: {out!r}"

    # Non-zero exit is a result to report, not an exception to raise.
    failed = terminal.run_command("ls no-such-file", cwd=project_dir)
    assert "exit code: 0" not in failed, f"expected non-zero exit: {failed!r}"
    assert "stderr" in failed, f"expected stderr to be surfaced: {failed!r}"

    # A cwd that resolves inside a root but isn't a directory is still an error.
    try:
        terminal.run_command("ls", cwd=str(Path(project_dir) / "nope"))
        raise AssertionError("expected NotADirectoryError for a non-existent cwd")
    except NotADirectoryError:
        pass


def check_sandbox(terminal, project_dir: str) -> None:
    try:
        terminal.run_command("ls", cwd="/etc")
        raise AssertionError("expected PermissionError for a cwd outside the roots")
    except PermissionError:
        pass

    try:
        terminal.run_command("ls | wc -l", cwd=project_dir)
        raise AssertionError("expected ValueError for a piped command")
    except ValueError:
        pass

    try:
        terminal.run_command("definitely-not-a-real-binary", cwd=project_dir)
        raise AssertionError("expected FileNotFoundError for an unknown binary")
    except FileNotFoundError:
        pass


def check_limits(terminal, project_dir: str) -> None:
    terminal.MAX_OUTPUT_CHARS = 500
    big = Path(project_dir) / "big.txt"
    big.write_text("x" * 5_000)
    capped = terminal.run_command(f"cat {big}", cwd=project_dir)
    assert "truncated at 500 chars" in capped, f"output was not capped: {capped[:200]!r}"
    assert len(capped) < 1_000, f"capped output still too long: {len(capped)}"

    terminal.TIMEOUT_SECONDS = 1
    try:
        terminal.run_command("sleep 5", cwd=project_dir)
        raise AssertionError("expected TimeoutError for a command over the limit")
    except TimeoutError:
        pass


def check_allowlist(permissions, project_dir: str) -> None:
    allowed = [
        "ls",
        "ls -la",
        "pwd",
        "git status",
        "git log --oneline -20",
        "grep -rn 'todo' .",
        f"cat {project_dir}/sentinel.txt",  # absolute, but inside a root
    ]
    for cmd in allowed:
        assert permissions.is_command_allowlisted(cmd), f"should not need confirmation: {cmd!r}"

    denied = [
        "rm -rf .",              # not read-only
        "npm install",           # not read-only
        "git push",              # git, but not a read-only subcommand
        "git -C /tmp status",    # -C escapes the sandboxed cwd
        "find . -delete",        # read-only command, writing flag
        "find . -exec rm {} ;",  # read-only command, executing flag
        "cat /etc/passwd",       # allowlisted command, path outside the roots
        "cat ../../secrets.txt", # allowlisted command, traversal out of the roots
        "'unclosed quote",       # unparseable
        "",                      # empty
    ]
    for cmd in denied:
        assert not permissions.is_command_allowlisted(cmd), f"should need confirmation: {cmd!r}"


def check_gate(permissions, registry) -> None:
    """The gate must auto-approve allowlisted commands and prompt for the
    rest — without any tool deciding that for itself."""
    tool = registry.get("run_command")
    assert tool.tier == 2, f"run_command should be tier 2, got {tool.tier}"

    asked: list[dict] = []

    def fake_confirmation(t, args):
        asked.append(args)
        return False

    permissions.request_confirmation = fake_confirmation
    log = permissions.ActivityLog(path=Path(os.environ["TARS_SMOKE_LOG"]))

    assert permissions.gate(tool, {"command": "git status"}, log), "allowlisted command was gated"
    assert asked == [], "allowlisted command should never reach the confirmation prompt"

    assert not permissions.gate(tool, {"command": "rm -rf /"}, log), "denial was not honoured"
    assert len(asked) == 1, f"expected exactly one confirmation prompt, got {len(asked)}"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as project_dir:
        os.environ["TARS_DB_PATH"] = str(Path(tmp_dir) / "smoke.db")
        os.environ["TARS_SMOKE_LOG"] = str(Path(tmp_dir) / "activity.jsonl")

        from db import db
        from tools import build_registry
        import tools.permissions as permissions
        import tools.terminal as terminal

        db.init_db()
        db.create_project("Smoke Project", root_path=project_dir)

        check_execution(terminal, project_dir)
        check_sandbox(terminal, project_dir)
        check_limits(terminal, project_dir)
        check_allowlist(permissions, project_dir)
        check_gate(permissions, build_registry())

    print("SMOKE TERMINAL: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - surface any failure clearly, then exit non-zero
        print(f"SMOKE TERMINAL: FAILED - {e}", file=sys.stderr)
        sys.exit(1)
