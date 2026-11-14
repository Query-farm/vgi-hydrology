"""Loopback-only, synthetic inventory for the released starter-schema REST reader."""

from __future__ import annotations

import atexit
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Public, deliberately fake credential; no real account or environment is consulted.
FIXTURE_TOKEN = "synthetic-hydrology-notebook-only"
ITEMS = [
    {"id": 1, "name": "Gauge", "category": "hardware", "price": 120.0},
    {"id": 2, "name": "Cable", "category": "hardware", "price": 15.0},
    {"id": 3, "name": "Mapping license", "category": "software", "price": 60.0},
    {"id": 4, "name": "Mount", "category": "hardware", "price": 25.0},
    {"id": 5, "name": "Battery", "category": "hardware", "price": None},
    {"id": 6, "name": None, "category": "service", "price": 45.0},
    {"id": 7, "name": "Logger", "category": "hardware", "price": 85.0},
]


class InventoryFixture:
    """Serve fixed pages, require the fake token, and retain token-free request evidence."""

    def __init__(self) -> None:
        """Bind an ephemeral IPv4 loopback port and start a daemon request thread."""
        self.requests: list[dict[str, int]] = []
        audit = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                """Keep ordinary server logs and headers out of notebook output."""

            def do_GET(self) -> None:  # noqa: N802
                """Return one page of fixed rows; do not implement any write operation."""
                url = urlparse(self.path)
                status = 200
                page = page_size = 0
                if url.path != "/items":
                    status, body = 404, {"error": "fixture route not found"}
                elif self.headers.get("Authorization") != f"Bearer {FIXTURE_TOKEN}":
                    status, body = 401, {"error": "fixture credential required"}
                else:
                    try:
                        args = parse_qs(url.query)
                        page = int(args.get("page", ["1"])[0])
                        page_size = int(args.get("page_size", ["100"])[0])
                        if page < 1 or not 1 <= page_size <= 1000:
                            raise ValueError
                    except (ValueError, IndexError):
                        status, body = 400, {"error": "invalid fixture pagination"}
                    else:
                        start = (page - 1) * page_size
                        body = {
                            "items": ITEMS[start : start + page_size],
                            "next_page": page + 1 if start + page_size < len(ITEMS) else None,
                        }
                audit.append({"page": page, "page_size": page_size, "status": status})
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self._closed = False
        atexit.register(self.close)

    def close(self) -> None:
        """Stop listening and release the fixture port; repeated cleanup is harmless."""
        if not self._closed:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self._closed = True
