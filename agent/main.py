"""CLI entry point for testing the agent loop end-to-end before wiring it
into the Tauri frontend. Run this first — see HANDOFF.md next steps.

    python3 main.py
"""

from __future__ import annotations

import sys

from db.db import init_db
from model_client import ModelClient
from orchestrator import Orchestrator
from tools import build_registry


def main() -> None:
    client = ModelClient()
    if not client.is_reachable():
        print(
            "Can't reach Ollama at 127.0.0.1:11434. Is it running? "
            "(`ollama serve`, then `ollama pull gemma4:12b` if you haven't yet.)"
        )
        sys.exit(1)

    init_db()
    registry = build_registry()
    orchestrator = Orchestrator(client, registry)

    print("TARS (scaffold build). Type 'exit' to quit.\n")
    history: list[dict] = []
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        answer = orchestrator.run(user_input, history)
        print(f"tars> {answer}\n")
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
