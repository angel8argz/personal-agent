"""SQLite access layer for projects/tasks. Each function opens and closes
its own connection via get_connection().
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "tars.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

VALID_STATUSES = {"todo", "in_progress", "done"}


def db_path() -> Path:
    """Resolved at call time (not import time) so tests can set
    TARS_DB_PATH after this module is imported."""
    override = os.environ.get("TARS_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript(SCHEMA_PATH.read_text())
    conn.close()


def create_project(name: str, description: str = "", root_path: str = "") -> int:
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO projects (name, description, root_path) VALUES (?, ?, ?)",
                (name, description, root_path),
            )
            return cur.lastrowid
    finally:
        conn.close()


def list_projects() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    finally:
        conn.close()


def get_project(project_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    finally:
        conn.close()


def delete_project(project_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    finally:
        conn.close()


def create_task(project_id: int, title: str, notes: str = "", due_date: str | None = None) -> int:
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO tasks (project_id, title, notes, due_date) VALUES (?, ?, ?, ?)",
                (project_id, title, notes, due_date),
            )
            return cur.lastrowid
    finally:
        conn.close()


def list_tasks(project_id: int | None = None, status: str | None = None) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id"
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def list_upcoming_tasks(within_days: int = 7) -> list[sqlite3.Row]:
    """Tasks due within `within_days` from today (inclusive), not done,
    ordered by due_date."""
    conn = get_connection()
    try:
        today = date.today()
        cutoff = today + timedelta(days=within_days)
        return conn.execute(
            "SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date >= ? "
            "AND due_date <= ? AND status != 'done' ORDER BY due_date",
            (today.isoformat(), cutoff.isoformat()),
        ).fetchall()
    finally:
        conn.close()


def update_task_status(task_id: int, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}, must be one of {sorted(VALID_STATUSES)}")
    conn = get_connection()
    try:
        with conn:
            if status == "done":
                conn.execute(
                    "UPDATE tasks SET status = ?, completed_at = datetime('now') WHERE id = ?",
                    (status, task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ?, completed_at = NULL WHERE id = ?",
                    (status, task_id),
                )
    finally:
        conn.close()


def list_project_roots() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT root_path FROM projects WHERE root_path IS NOT NULL AND root_path != ''"
        ).fetchall()
        return [r["root_path"] for r in rows]
    finally:
        conn.close()
