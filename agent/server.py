"""Stdlib-only local HTTP server exposing the agent to the Tauri frontend.
See IMPLEMENTATION.md "Decision - Step 3 transport": no new dependency, bound
to 127.0.0.1 only, per HANDOFF.md's starting recommendation.

Run:
    agent/.venv/bin/python agent/server.py
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))

from chat_session import ChatSession  # noqa: E402
from confirmations import ConfirmationBroker  # noqa: E402
from db import db  # noqa: E402

HOST = "127.0.0.1"
# 8765 by default, but nothing reserves that port — set TARS_PORT to move it,
# and VITE_AGENT_BASE on the frontend to match.
PORT = int(os.environ.get("TARS_PORT", "8765"))

MAX_BODY_BYTES = 256 * 1024

# Binding to loopback keeps other machines out, but not other *pages* on this
# one: any site the user visits could fetch these routes. Now that writes and
# tool approvals live here, a background tab must not be able to register a
# project root or approve a Tier 2 command — so the origin is checked
# explicitly, replacing the `Access-Control-Allow-Origin: *` this server
# started with. A missing Origin (curl, the smoke tests, same-origin GETs) is
# allowed; a present-but-unrecognised one is refused.
ALLOWED_ORIGINS = {
    "http://localhost:1420",   # vite dev server (frontend/vite.config.ts)
    "http://127.0.0.1:1420",
    "tauri://localhost",       # packaged macOS webview
    "http://tauri.localhost",
}

# Installed by main() / attach_agent(). The read-only routes work without them.
broker: ConfirmationBroker | None = None
session: ChatSession | None = None


def attach_agent(chat_session: ChatSession, confirmation_broker: ConfirmationBroker) -> None:
    """Wire in the chat + confirmation machinery. Without this, the server
    still serves the read-only dashboard routes."""
    global session, broker
    session = chat_session
    broker = confirmation_broker


class Handler(BaseHTTPRequestHandler):
    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in ALLOWED_ORIGINS

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def do_OPTIONS(self) -> None:  # noqa: N802 - required name
        if not self._origin_allowed():
            self._send_json(403, {"error": "origin not allowed"})
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - required name by BaseHTTPRequestHandler
        if not self._origin_allowed():
            self._send_json(403, {"error": "origin not allowed"})
            return

        parsed = urlparse(self.path)
        if parsed.path == "/projects":
            rows = [dict(r) for r in db.list_projects()]
            self._send_json(200, rows)
            return
        if parsed.path == "/tasks/upcoming":
            qs = parse_qs(parsed.query)
            raw = qs.get("within_days", ["7"])[0]
            try:
                within_days = int(raw)
            except (TypeError, ValueError):
                within_days = 7
            rows = [dict(r) for r in db.list_upcoming_tasks(within_days)]
            self._send_json(200, rows)
            return
        if parsed.path == "/chat/run":
            self._handle_run_status(parse_qs(parsed.query))
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - required name
        if not self._origin_allowed():
            self._send_json(403, {"error": "origin not allowed"})
            return

        parsed = urlparse(self.path)
        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"error": "expected a JSON object body"})
            return

        if parsed.path == "/projects":
            self._handle_create_project(payload)
            return
        if parsed.path == "/chat":
            self._handle_chat(payload)
            return
        if parsed.path == "/chat/confirm":
            self._handle_confirm(payload)
            return
        self._send_json(404, {"error": "not found"})

    # --- route handlers --------------------------------------------------

    def _handle_create_project(self, payload: dict) -> None:
        name = str(payload.get("name", "")).strip()
        if not name:
            self._send_json(400, {"error": "name is required"})
            return
        root_path = str(payload.get("root_path", "")).strip()
        if root_path:
            # Registering a root is what grants the tools access to it, so
            # refuse a path that isn't a directory rather than silently
            # registering a typo the tools will reject later.
            candidate = Path(root_path).expanduser()
            if not candidate.is_dir():
                self._send_json(400, {"error": f"not a directory: {root_path}"})
                return
            root_path = str(candidate.resolve())
        project_id = db.create_project(
            name, description=str(payload.get("description", "")), root_path=root_path
        )
        self._send_json(201, {"id": project_id})

    def _handle_chat(self, payload: dict) -> None:
        if session is None:
            self._send_json(503, {"error": "no agent attached to this server"})
            return
        message = str(payload.get("message", "")).strip()
        if not message:
            self._send_json(400, {"error": "message is required"})
            return
        self._send_json(202, {"run_id": session.start(message)})

    def _handle_run_status(self, qs: dict) -> None:
        if session is None:
            self._send_json(503, {"error": "no agent attached to this server"})
            return
        try:
            run_id = int(qs.get("id", [""])[0])
        except (TypeError, ValueError):
            self._send_json(400, {"error": "id must be an integer"})
            return
        run = session.status(run_id)
        if run is None:
            self._send_json(404, {"error": f"no such run: {run_id}"})
            return
        run["pending"] = broker.pending() if broker is not None else []
        self._send_json(200, run)

    def _handle_confirm(self, payload: dict) -> None:
        if broker is None:
            self._send_json(503, {"error": "no agent attached to this server"})
            return
        try:
            confirmation_id = int(payload.get("id"))
        except (TypeError, ValueError):
            self._send_json(400, {"error": "id must be an integer"})
            return
        if not isinstance(payload.get("approved"), bool):
            self._send_json(400, {"error": "approved must be a boolean"})
            return
        resolved = broker.resolve(confirmation_id, payload["approved"])
        self._send_json(200 if resolved else 404, {"resolved": resolved})

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - silence default stderr logging
        pass


def serve(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    return server


def main() -> None:
    from model_client import ModelClient
    from orchestrator import Orchestrator
    from tools import build_registry
    from tools.permissions import set_confirmation_provider

    db.init_db()

    confirmation_broker = ConfirmationBroker()
    set_confirmation_provider(
        lambda tool_name, tier, args: confirmation_broker.request(tool_name, tier, args)
    )
    attach_agent(
        ChatSession(Orchestrator(ModelClient(), build_registry())), confirmation_broker
    )

    httpd = serve()
    print(f"TARS agent server listening on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
