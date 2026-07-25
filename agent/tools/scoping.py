"""Where tools are allowed to touch: the registered project roots.

Shared by Tier 1 (tools/file_tools.py) and Tier 2 (tools/terminal.py) so both
tiers enforce the same sandbox boundary rather than each growing its own.
"""

from __future__ import annotations

from pathlib import Path

from db.db import list_project_roots


def project_roots() -> list[Path]:
    return [Path(r).expanduser().resolve() for r in list_project_roots()]


def is_within_project_roots(path: Path) -> bool:
    """Non-raising containment check, for callers deciding *how* to proceed
    rather than *whether* to (see permissions.is_command_allowlisted)."""
    for root in project_roots():
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def resolve_within_project_roots(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    roots = project_roots()
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
