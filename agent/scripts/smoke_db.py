"""Non-interactive smoke test for db.db CRUD + the file_tools sandbox.

Run:
    agent/.venv/bin/python agent/scripts/smoke_db.py

Exits 0 with "SMOKE DB: OK" on success, non-zero with a message on failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_db_dir, tempfile.TemporaryDirectory() as project_dir:
        os.environ["TARS_DB_PATH"] = str(Path(tmp_db_dir) / "smoke.db")

        from db import db
        import tools.file_tools as file_tools

        db.init_db()

        project_id = db.create_project("Smoke Project", root_path=project_dir)

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        far_out = (date.today() + timedelta(days=30)).isoformat()

        tomorrow_task = db.create_task(project_id, "due tomorrow", due_date=tomorrow)
        db.create_task(project_id, "due in 30 days", due_date=far_out)
        db.create_task(project_id, "no due date")

        upcoming = db.list_upcoming_tasks(7)
        assert len(upcoming) == 1, f"expected exactly 1 upcoming task, got {len(upcoming)}"
        assert upcoming[0]["id"] == tomorrow_task, "wrong task returned as upcoming"

        db.update_task_status(tomorrow_task, "done")
        done_tasks = db.list_tasks(project_id=project_id, status="done")
        assert len(done_tasks) == 1, "expected 1 done task"
        assert done_tasks[0]["completed_at"] is not None, "completed_at was not set on completion"

        roots = db.list_project_roots()
        assert roots == [project_dir], f"unexpected project roots: {roots}"

        sentinel_path = Path(project_dir) / "sentinel.txt"
        sentinel_path.write_text("hello from smoke test")
        content = file_tools.read_file(str(sentinel_path))
        assert content == "hello from smoke test", f"read_file content mismatch: {content!r}"

        try:
            file_tools.read_file("/etc/hosts")
            raise AssertionError("expected PermissionError reading a path outside registered roots")
        except PermissionError:
            pass

        db.delete_project(project_id)
        remaining = db.list_tasks(project_id=project_id)
        assert remaining == [], f"tasks were not cascade-deleted with their project: {remaining}"

        try:
            file_tools.read_file(str(sentinel_path))
            raise AssertionError("expected PermissionError once no project roots are registered")
        except PermissionError:
            pass

    print("SMOKE DB: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - surface any failure clearly, then exit non-zero
        print(f"SMOKE DB: FAILED - {e}", file=sys.stderr)
        sys.exit(1)
