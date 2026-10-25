"""Shared fixtures: the default rules and a small fake OpenAI-compatible endpoint."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from bookkeywordlab.rules import load_rules


@pytest.fixture(scope="session")
def default_rules():
    return load_rules(None)


class _EndpointFactory:
    """Spins up 127.0.0.1:<ephemeral>/v1 which speaks /chat/completions + /models."""

    def __init__(self):
        self.last_headers = {}
        self.last_body = {}

    def make(self, content=None, model_ids=None):
        factory = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _send(self, code, body):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                factory.last_headers = dict(self.headers)
                if self.path.rstrip("/").endswith("/models"):
                    ids = model_ids if model_ids is not None else ["llama3.2", "mistral"]
                    self._send(200, json.dumps({"data": [{"id": i} for i in ids]}).encode())
                else:
                    self._send(404, b'{"error": "no route"}')

            def do_POST(self):
                size = int(self.headers.get("Content-Length", 0))
                try:
                    factory.last_body = json.loads(self.rfile.read(size) or b"{}")
                except ValueError:
                    factory.last_body = {}
                factory.last_headers = dict(self.headers)
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self._send(404, b'{"error": "no route"}')
                    return
                text = json.dumps(content if content is not None else ["ai for beginners"])
                payload = {"choices": [{"message": {"content": text}}]}
                self._send(200, json.dumps(payload).encode())

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/v1"

        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        return SimpleNamespace(base_url=base, holder=factory, close=close)


@pytest.fixture()
def endpoint_factory():
    factory = _EndpointFactory()
    handles = []

    def make(*args, **kwargs):
        handle = factory.make(*args, **kwargs)
        handles.append(handle)
        return handle

    yield make
    for handle in handles:
        handle.close()
