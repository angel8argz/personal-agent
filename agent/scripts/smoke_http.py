"""Non-interactive smoke test for agent/server.py.

Run:
    agent/.venv/bin/python agent/scripts/smoke_http.py

Exits 0 with "SMOKE HTTP: OK" on success, non-zero with a clear message on
failure.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.request
from datetime import date, timedelta
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

HOST = "127.0.0.1"
PORT = 8766  # distinct from the real server's fixed 8765, to avoid clashing
             # with a dev instance that may already be running


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_db_dir:
        os.environ["TARS_DB_PATH"] = str(Path(tmp_db_dir) / "smoke_http.db")

        from db import db
        import server

        db.init_db()

        project_name = "Smoke HTTP Project"
        project_id = db.create_project(project_name)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        task_title = "smoke http due tomorrow"
        db.create_task(project_id, task_title, due_date=tomorrow)

        httpd = server.serve(HOST, PORT)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://{HOST}:{PORT}/projects", timeout=5
            ) as resp:
                assert resp.status == 200, f"expected 200, got {resp.status}"
                projects = json.loads(resp.read())
            names = [p["name"] for p in projects]
            assert project_name in names, f"project not found in {names}"

            with urllib.request.urlopen(
                f"http://{HOST}:{PORT}/tasks/upcoming?within_days=7", timeout=5
            ) as resp:
                assert resp.status == 200, f"expected 200, got {resp.status}"
                tasks = json.loads(resp.read())
            titles = [t["title"] for t in tasks]
            assert task_title in titles, f"task not found in {titles}"
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    print("SMOKE HTTP: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - surface any failure clearly, then exit non-zero
        print(f"SMOKE HTTP: FAILED - {e}", file=sys.stderr)
        sys.exit(1)
