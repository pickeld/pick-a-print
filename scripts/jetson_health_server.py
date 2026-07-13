#!/usr/bin/env python3
"""Minimal HTTP health endpoint for remote Jetson reachability checks."""
from __future__ import annotations

import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EXPECTED_TOKEN = os.getenv("JETSON_HEALTH_TOKEN", "").strip()


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _authorized(self) -> bool:
        if not EXPECTED_TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        provided = auth[7:].strip()
        return secrets.compare_digest(provided, EXPECTED_TOKEN)

    def do_GET(self):
        if self.path.rstrip("/") != "/health":
            self.send_error(404)
            return
        if not self._authorized():
            self.send_error(401)
            return
        body = json.dumps(
            {
                "status": "ok",
                "service": "pick-a-print-jetson",
                "auth": "required" if EXPECTED_TOKEN else "disabled",
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.getenv("JETSON_HEALTH_PORT", "8765"))
    host = os.getenv("JETSON_HEALTH_BIND", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), HealthHandler)
    if EXPECTED_TOKEN:
        print(f"Jetson health server on {host}:{port} (auth enabled)", flush=True)
    else:
        print(f"Jetson health server on {host}:{port} (auth disabled — set JETSON_HEALTH_TOKEN)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
