"""Shared fixtures: a local SponsorBlock server."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest


class FakeSponsorBlock(HTTPServer):
    """A local SponsorBlock: answers every request with `status` and `body`, records the paths."""

    status = 200
    body = b"[]"

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.paths: list[str] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class Handler(BaseHTTPRequestHandler):
    server: FakeSponsorBlock

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        self.server.paths.append(self.path)
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.server.body)))
        self.end_headers()
        self.wfile.write(self.server.body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeSponsorBlock]:
    for name in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.delenv(name, raising=False)
    fake = FakeSponsorBlock()
    thread = threading.Thread(target=fake.serve_forever, daemon=True)
    thread.start()
    yield fake
    fake.shutdown()
    fake.server_close()
