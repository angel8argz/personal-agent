"""The permission gate every tool call must pass through before executing.

This is deliberately the single choke point described in
docs/ARCHITECTURE.md — don't let tools bypass it.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from tools.base import Tool

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
    approved = request_confirmation(tool, args)
    if not approved:
        log.record(tool.name, tool.tier, args, approved=False, result="denied by user")
    return approved
