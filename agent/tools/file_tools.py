"""Tier 1 tools: file & project operations, scoped to registered project dirs.

The pattern to follow for the other tiers: plain functions plus a `Tool`
declaration at the bottom, with the sandbox boundary enforced through
tools/scoping.py. Tier 2 lives in tools/terminal.py; Tiers 3-4 are still
stubs in tools/stubs.py.
"""

from __future__ import annotations

from tools.base import Tool
from tools.scoping import resolve_within_project_roots


def read_file(path: str) -> str:
    target = resolve_within_project_roots(path)
    if not target.is_file():
        raise FileNotFoundError(f"No such file: {target}")
    return target.read_text(errors="replace")[:20_000]  # cap for context safety


def list_directory(path: str) -> str:
    target = resolve_within_project_roots(path)
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {target}")
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    return "\n".join(entries) or "(empty directory)"


def write_file(path: str, content: str) -> str:
    target = resolve_within_project_roots(path)
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
