import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.check_endpoints import verify_endpoints


@pytest.fixture
def endpoint_server():
    responses = {
        "/health": (200, {"status": "ok"}),
        "/ready": (200, {"status": "ready", "database": "ok", "redis": "ok"}),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = responses[self.path]
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", responses
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_checker_accepts_healthy_http_responses(endpoint_server):
    base_url, _ = endpoint_server
    verify_endpoints(base_url, timeout=1)


def test_checker_accepts_503_details_and_independent_health(endpoint_server):
    base_url, responses = endpoint_server
    responses["/ready"] = (
        503,
        {"status": "not_ready", "database": "unavailable", "redis": "unavailable"},
    )
    verify_endpoints(base_url, timeout=1, expect_unavailable=True)


@pytest.mark.parametrize(
    ("path", "response"),
    [
        ("/health", (503, {"status": "ok"})),
        ("/ready", (503, {"status": "ready", "database": "ok", "redis": "ok"})),
        ("/ready", (200, {"status": "ready", "database": "ok"})),
    ],
)
def test_checker_fails_within_deadline_on_incorrect_http_results(endpoint_server, path, response):
    base_url, responses = endpoint_server
    responses[path] = response
    with pytest.raises(TimeoutError, match="did not pass within 0.05s"):
        verify_endpoints(base_url, timeout=0.05)
