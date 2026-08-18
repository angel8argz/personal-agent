"""Non-interactive smoke test for the write routes, the origin check, and the
out-of-band confirmation round-trip.

Run:
    agent/.venv/bin/python agent/scripts/smoke_confirm.py

Exits 0 with "SMOKE CONFIRM: OK" on success. Uses a fake orchestrator, so no
Ollama and no model are involved.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

HOST = "127.0.0.1"
GOOD_ORIGIN = "http://localhost:1420"
BAD_ORIGIN = "https://evil.example.com"


def post(port: int, path: str, payload: dict, origin: str | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://{HOST}:{port}{path}", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    if origin:
        req.add_header("Origin", origin)
    return _send(req)


def get(port: int, path: str, origin: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://{HOST}:{port}{path}")
    if origin:
        req.add_header("Origin", origin)
    return _send(req)


def _send(req) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def check_broker_fails_closed(confirmations) -> None:
    """A decision that never arrives must deny, never approve."""
    broker = confirmations.ConfirmationBroker(timeout_seconds=0.2)
    assert broker.request("run_command", 2, {"command": "rm -rf /"}) is False, (
        "an unanswered confirmation must time out as a denial"
    )
    assert broker.pending() == [], "timed-out confirmation was left in the pending list"
    assert broker.resolve(999, True) is False, "resolving an unknown id should report failure"


def check_origin_enforced(port: int) -> None:
    status, _ = get(port, "/projects", origin=BAD_ORIGIN)
    assert status == 403, f"a foreign origin must be refused, got {status}"

    status, _ = post(port, "/projects", {"name": "x"}, origin=BAD_ORIGIN)
    assert status == 403, f"a foreign origin must not be able to write, got {status}"

    status, _ = get(port, "/projects", origin=GOOD_ORIGIN)
    assert status == 200, f"the dev origin must be allowed, got {status}"

    status, _ = get(port, "/projects")
    assert status == 200, f"a request with no Origin must be allowed, got {status}"


def check_create_project(port: int, project_dir: str) -> None:
    status, body = post(port, "/projects", {"name": ""}, origin=GOOD_ORIGIN)
    assert status == 400, f"an empty name must be rejected, got {status}"

    status, body = post(
        port, "/projects",
        {"name": "Typo", "root_path": project_dir + "/does-not-exist"},
        origin=GOOD_ORIGIN,
    )
    assert status == 400, f"a non-directory root_path must be rejected, got {status} {body}"

    status, body = post(
        port, "/projects",
        {"name": "Registered", "root_path": project_dir},
        origin=GOOD_ORIGIN,
    )
    assert status == 201, f"expected 201, got {status} {body}"

    status, projects = get(port, "/projects", origin=GOOD_ORIGIN)
    names = [p["name"] for p in projects]
    assert "Registered" in names, f"project not persisted: {names}"
    assert "Typo" not in names, f"rejected project was still written: {names}"


def check_confirmation_round_trip(port: int, approved: bool) -> None:
    """POST /chat -> the fake tool call blocks -> it shows up in
    /chat/run's pending list -> POST /chat/confirm releases it."""
    status, body = post(port, "/chat", {"message": "do the thing"}, origin=GOOD_ORIGIN)
    assert status == 202, f"expected 202 from /chat, got {status} {body}"
    run_id = body["run_id"]

    pending = _wait_for(
        lambda: get(port, f"/chat/run?id={run_id}", origin=GOOD_ORIGIN)[1].get("pending"),
        "a pending confirmation to appear",
    )
    entry = pending[0]
    assert entry["tier"] == 2, f"tier should survive the round-trip: {entry}"
    assert entry["args"]["command"] == "ls -la", f"args should survive: {entry}"

    status, body = post(
        port, "/chat/confirm", {"id": entry["id"], "approved": approved}, origin=GOOD_ORIGIN
    )
    assert status == 200 and body["resolved"], f"confirm failed: {status} {body}"

    run = _wait_for(
        lambda: (lambda r: r if r.get("status") == "done" else None)(
            get(port, f"/chat/run?id={run_id}", origin=GOOD_ORIGIN)[1]
        ),
        "the run to finish",
    )
    expected = "approved" if approved else "denied"
    assert run["answer"] == expected, f"expected {expected!r}, got {run['answer']!r}"


def check_confirm_validation(port: int) -> None:
    status, _ = post(port, "/chat/confirm", {"id": "abc", "approved": True}, origin=GOOD_ORIGIN)
    assert status == 400, f"a non-integer id must be rejected, got {status}"

    status, _ = post(port, "/chat/confirm", {"id": 1}, origin=GOOD_ORIGIN)
    assert status == 400, f"a missing 'approved' must be rejected, got {status}"

    status, body = post(port, "/chat/confirm", {"id": 4242, "approved": True}, origin=GOOD_ORIGIN)
    assert status == 404 and not body["resolved"], f"unknown id should 404, got {status} {body}"

    status, _ = get(port, "/chat/run?id=nope", origin=GOOD_ORIGIN)
    assert status == 400, f"a non-integer run id must be rejected, got {status}"


def _wait_for(probe, description: str, attempts: int = 100):
    """Poll `probe` until it returns something truthy. No `timeout` binary on
    this machine and no sleep-free way to await a worker thread, so this is a
    bounded poll rather than a wait/notify."""
    import time

    for _ in range(attempts):
        value = probe()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {description}")


class FakeOrchestrator:
    """Stands in for the real orchestrator: asks for confirmation of one
    Tier 2 call and reports the verdict, with no model involved."""

    def __init__(self, broker):
        self.broker = broker

    def run(self, message: str, history: list[dict] | None = None) -> str:
        approved = self.broker.request("run_command", 2, {"command": "ls -la"})
        return "approved" if approved else "denied"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as project_dir:
        os.environ["TARS_DB_PATH"] = str(Path(tmp_dir) / "smoke_confirm.db")

        import confirmations
        import server
        from chat_session import ChatSession
        from db import db

        db.init_db()

        check_broker_fails_closed(confirmations)

        broker = confirmations.ConfirmationBroker(timeout_seconds=10)
        server.attach_agent(ChatSession(FakeOrchestrator(broker)), broker)

        httpd = server.serve(HOST, 0)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            check_origin_enforced(port)
            check_create_project(port, project_dir)
            check_confirmation_round_trip(port, approved=True)
            check_confirmation_round_trip(port, approved=False)
            check_confirm_validation(port)
        finally:
            httpd.shutdown()
            httpd.server_close()

    print("SMOKE CONFIRM: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - surface any failure clearly, then exit non-zero
        print(f"SMOKE CONFIRM: FAILED - {e}", file=sys.stderr)
        sys.exit(1)
