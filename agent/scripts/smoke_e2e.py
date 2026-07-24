"""End-to-end smoke test: orchestrator + real Ollama model + Tier 1 file
tools wired to a registered project.

Run:
    agent/.venv/bin/python agent/scripts/smoke_e2e.py

Prints "SMOKE E2E: OK" and exits 0 on success. If Ollama isn't reachable or
the default model isn't pulled, prints a SKIP message and exits 2 (distinct
from a real failure). Any other failure exits 1.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

SENTINEL_LINE = "SENTINEL-7391: the launch code is banana"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_db_dir, tempfile.TemporaryDirectory() as project_dir:
        os.environ["TARS_DB_PATH"] = str(Path(tmp_db_dir) / "smoke.db")

        import requests

        from db import db
        from model_client import ModelClient
        from orchestrator import Orchestrator
        from tools import build_registry
        from tools.permissions import ACTIVITY_LOG_PATH

        db.init_db()

        notes_path = Path(project_dir) / "notes.txt"
        notes_path.write_text(SENTINEL_LINE)
        db.create_project("E2E Smoke Project", root_path=project_dir)

        client = ModelClient()
        if not client.is_reachable():
            print("SMOKE E2E: SKIP - Ollama not reachable at 127.0.0.1:11434")
            sys.exit(2)

        tags = requests.get(f"{client.host}/api/tags", timeout=5).json()
        model_names = {m.get("name") for m in tags.get("models", [])}
        if client.model not in model_names:
            print(f"SMOKE E2E: SKIP - model '{client.model}' not found via /api/tags")
            sys.exit(2)

        log_before = ACTIVITY_LOG_PATH.read_text() if ACTIVITY_LOG_PATH.exists() else ""

        registry = build_registry()
        orchestrator = Orchestrator(client, registry)
        answer = orchestrator.run(
            f"Read the file {notes_path} and tell me exactly what the SENTINEL line says."
        )

        assert "SENTINEL-7391" in answer or "banana" in answer, (
            f"answer did not mention the sentinel: {answer!r}"
        )

        log_after = ACTIVITY_LOG_PATH.read_text() if ACTIVITY_LOG_PATH.exists() else ""
        assert len(log_after) > len(log_before), "activity log did not gain an entry during the run"

    print("SMOKE E2E: OK")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - surface any failure clearly, then exit non-zero
        print(f"SMOKE E2E: FAILED - {e}", file=sys.stderr)
        sys.exit(1)
