"""Check the running HTTP server, including dependency failure and recovery."""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def read_response(url: str, timeout: float) -> tuple[int, object]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as error:
        # HTTP 503 still has dependency results that must be checked.
        response = error
    with response:
        return response.status, json.load(response)


def verify_endpoints(
    base_url: str = "http://127.0.0.1:8000",
    *,
    timeout: float = 60,
    expect_unavailable: bool = False,
) -> None:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    expected_ready = (
        (503, {"status": "not_ready", "database": "unavailable", "redis": "unavailable"})
        if expect_unavailable
        else (200, {"status": "ready", "database": "ok", "redis": "ok"})
    )
    expected = {"/health": (200, {"status": "ok"}), "/ready": expected_ready}
    deadline = time.monotonic() + timeout
    last_failure = "No response received"

    while time.monotonic() < deadline:
        try:
            for path, expected_response in expected.items():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Endpoint check deadline reached")
                # Failed dependency lookups can take longer than healthy requests.
                # Give each request the remaining overall budget, not a shorter
                # limit that would discard every valid HTTP 503 response.
                actual = read_response(base_url.rstrip("/") + path, remaining)
                if actual != expected_response:
                    raise ValueError(f"{path}: expected {expected_response!r}; got {actual!r}")
            print(f"/health: HTTP 200, status ok; /ready: HTTP {expected_ready[0]}, {expected_ready[1]}")
            return
        except (URLError, OSError, ValueError) as error:
            last_failure = str(error)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(1, remaining))

    raise TimeoutError(f"Endpoint checks did not pass within {timeout:g}s: {last_failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--expect-unavailable", action="store_true")
    arguments = parser.parse_args()
    try:
        verify_endpoints(timeout=arguments.timeout, expect_unavailable=arguments.expect_unavailable)
    except (TimeoutError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
