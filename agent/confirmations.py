"""Out-of-band tool confirmations, so the approval prompt can render in the
UI instead of on stdin.

The orchestrator is synchronous by design (docs/ARCHITECTURE.md), and stays
that way: when a tool call needs approval, the orchestrator thread blocks on
an Event while the HTTP layer surfaces the request and posts the answer back.
Nothing about orchestrator.py or the gate's shape changes.

Fails closed. A decision that never arrives is a denial, never an approval —
so a closed window or a crashed frontend can't leave a Tier 2+ call waiting
and then let it through.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field

DEFAULT_TIMEOUT_SECONDS = 300.0


@dataclass
class PendingConfirmation:
    id: int
    tool_name: str
    tier: int
    args: dict
    event: threading.Event = field(default_factory=threading.Event)
    approved: bool = False

    def as_json(self) -> dict:
        return {
            "id": self.id,
            "tool": self.tool_name,
            "tier": self.tier,
            "args": self.args,
        }


class ConfirmationBroker:
    """Bridges the orchestrator thread (blocking on a decision) and the HTTP
    layer (surfacing it, then answering)."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._pending: dict[int, PendingConfirmation] = {}
        self._ids = itertools.count(1)

    def request(self, tool_name: str, tier: int, args: dict) -> bool:
        """Called from the orchestrator thread. Blocks until answered or the
        timeout elapses; returns whether the call is approved."""
        with self._lock:
            entry = PendingConfirmation(
                id=next(self._ids), tool_name=tool_name, tier=tier, args=args
            )
            self._pending[entry.id] = entry
        try:
            if not entry.event.wait(self.timeout_seconds):
                return False  # timed out — deny
            return entry.approved
        finally:
            with self._lock:
                self._pending.pop(entry.id, None)

    def pending(self) -> list[dict]:
        with self._lock:
            return [e.as_json() for e in self._pending.values()]

    def resolve(self, confirmation_id: int, approved: bool) -> bool:
        """Called from an HTTP thread. False if there's no such pending
        confirmation (already answered, timed out, or never existed)."""
        with self._lock:
            entry = self._pending.get(confirmation_id)
        if entry is None:
            return False
        entry.approved = approved
        entry.event.set()
        return True
