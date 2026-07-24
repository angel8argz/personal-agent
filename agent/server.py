"""Stdlib-only local HTTP server exposing read-only DB endpoints to the
Tauri frontend. See IMPLEMENTATION.md "Decision - Step 3 transport": no new
dependency, bound to 127.0.0.1 only, per HANDOFF.md's starting recommendation.

Run:
    agent/.venv/bin/python agent/server.py
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))

from db import db  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - required name by BaseHTTPRequestHandler
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
        self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - silence default stderr logging
        pass


def serve(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    return server


if __name__ == "__main__":
    db.init_db()
    httpd = serve()
    print(f"TARS agent server listening on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
