"""One conversation with the agent, plus the runs inside it.

Each run is an orchestrator invocation on a worker thread, so the HTTP layer
stays responsive while a run sits waiting on a tool confirmation. Single
conversation, single user — docs/ARCHITECTURE.md's "no multi-user support".
"""

from __future__ import annotations

import itertools
import threading


class ChatSession:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._runs: dict[int, dict] = {}
        self._ids = itertools.count(1)

    def start(self, message: str) -> int:
        with self._lock:
            run_id = next(self._ids)
            self._runs[run_id] = {"status": "running", "answer": None, "error": None}
            history = list(self._history)
        thread = threading.Thread(
            target=self._execute, args=(run_id, message, history), daemon=True
        )
        thread.start()
        return run_id

    def _execute(self, run_id: int, message: str, history: list[dict]) -> None:
        try:
            answer = self.orchestrator.run(message, history)
        except Exception as e:  # noqa: BLE001 - a failed run is state, not a crash
            with self._lock:
                self._runs[run_id] = {"status": "error", "answer": None, "error": str(e)}
            return
        with self._lock:
            self._runs[run_id] = {"status": "done", "answer": answer, "error": None}
            self._history.append({"role": "user", "content": message})
            self._history.append({"role": "assistant", "content": answer})

    def status(self, run_id: int) -> dict | None:
        with self._lock:
            run = self._runs.get(run_id)
            return dict(run) if run is not None else None

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)
