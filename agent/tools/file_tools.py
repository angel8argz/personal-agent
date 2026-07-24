"""Tier 1 tools: file & project operations, scoped to registered project dirs.

These are the only tools in this scaffold with real (if minimal)
implementations — everything else is a stub. Use these as the pattern for
how Tier 2-4 tools should be shaped once they're built out.
"""

from __future__ import annotations

from pathlib import Path

from db.db import list_project_roots
from tools.base import Tool


def _resolve_within_allowed(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    roots = [Path(r).expanduser().resolve() for r in list_project_roots()]
    if not roots:
        raise PermissionError(
            "No project directories registered yet. Add one via the dashboard "
            "before TARS can touch files."
        )
    for root in roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise PermissionError(f"'{p}' is outside all registered project directories")


def read_file(path: str) -> str:
    target = _resolve_within_allowed(path)
    if not target.is_file():
        raise FileNotFoundError(f"No such file: {target}")
    return target.read_text(errors="replace")[:20_000]  # cap for context safety


def list_directory(path: str) -> str:
    target = _resolve_within_allowed(path)
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {target}")
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    return "\n".join(entries) or "(empty directory)"


def write_file(path: str, content: str) -> str:
    target = _resolve_within_allowed(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} chars to {target}"


TOOLS = [
    Tool(
        name="read_file",
        description="Read a text file within a registered project directory.",
        tier=1,
        parameters_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute or ~-relative file path"}},
            "required": ["path"],
        },
        fn=read_file,
    ),
    Tool(
        name="read_directory",  # named read_* so it's auto-approved by permissions.py
        description="List the contents of a directory within a registered project.",
        tier=1,
        parameters_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        fn=list_directory,
    ),
    Tool(
        name="write_file",
        description="Write or overwrite a text file within a registered project directory. Requires confirmation.",
        tier=1,
        parameters_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        fn=write_file,
    ),
]
