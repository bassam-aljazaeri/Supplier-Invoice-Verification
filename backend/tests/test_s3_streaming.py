"""Actual loopback HTTP/urllib3/StreamingBody lifecycle; no AWS or credentials."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import time
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

from botocore.response import StreamingBody
import pytest
from urllib3 import PoolManager, Timeout

from app.document_tasks import process_document
from app.storage import StorageIntegrity, StorageUnavailable, StoredObject
from app.storage.keys import CHUNK_SIZE, new_key
from app.storage.s3 import S3DocumentStorage
from tests.s3_helpers import BUCKET, PREFIX, REGION
from tests.document_helpers import pdf


@pytest.fixture
def http_object():
    plans, responses = [], []
    release = Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            payload, length, hold_open = plans.pop(0)
            self.send_response(200)
            self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
            if hold_open:
                release.wait(timeout=3)
            self.close_connection = True

        def log_message(self, *args):
            pass

    class Body(StreamingBody):
        def __init__(self, raw, length):
            super().__init__(raw, length)
            self.timeout_calls = []
            self.read_calls = []
            self.eof_reads = 0
            self.closed_by_adapter = False

        def set_socket_timeout(self, timeout):
            # Observe the real lifecycle, then delegate to the unmodified SDK.
            self.timeout_calls.append((self.tell(), self._raw_stream._fp.fp is None, timeout))
            return super().set_socket_timeout(timeout)

        def close(self):
            self.closed_by_adapter = True
            super().close()

        def read(self, amt=None):
            self.read_calls.append(amt)
            data = super().read(amt)
            if amt != 0 and not data:
                self.eof_reads += 1
            return data

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    pool = PoolManager(timeout=Timeout(connect=1, read=1), retries=False)

    def open_response(payload, *, declared_length=None, hold_open=False):
        length = len(payload) if declared_length is None else declared_length
        plans.append((payload, length, hold_open))
        raw = pool.request("GET", f"http://127.0.0.1:{server.server_port}/object", preload_content=False, decode_content=False)
        body = Body(raw, length)
        responses.append(body)
        return {"Body": body, "ContentLength": length}

    try:
        yield open_response
    finally:
        release.set()
        for body in responses:
            body.close()
        pool.clear()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def adapter_response(response):
    class Client:
        def get_object(self, **params):
            assert params["Bucket"] == BUCKET and params["Key"].startswith(PREFIX)
            return response
    return S3DocumentStorage(BUCKET, REGION, PREFIX, client=Client())


def test_real_sdk_timeout_setter_requires_a_live_socket_after_eof(http_object):
    payload = b"fictional small response"
    body = http_object(payload)["Body"]
    assert body._raw_stream._fp.fp is not None
    body.set_socket_timeout(1)
    assert body.read(CHUNK_SIZE) == payload
    # urllib3/http.client releases the socket when Content-Length is consumed,
    # even though the caller has not yet received an empty read.
    assert body._raw_stream._fp.fp is None
    assert body._raw_stream._connection is None
    with pytest.raises(AttributeError, match="raw"):
        body.set_socket_timeout(1)
    assert body.timeout_calls[-1][:2] == (len(payload), True)


@pytest.mark.parametrize("size", [23, CHUNK_SIZE, CHUNK_SIZE + 17])
@pytest.mark.parametrize("operation", ["stat", "read_all", "read_chunks", "exact_limit"])
def test_adapter_does_not_set_timeouts_on_a_socket_released_at_eof(http_object, size, operation):
    payload = b"x" * size
    response = http_object(payload)
    body, key = response["Body"], new_key(uuid4(), uuid4())
    adapter = adapter_response(response)
    if operation == "stat":
        assert adapter.stat(key) == StoredObject(size, hashlib.sha256(payload).hexdigest())
    else:
        # The worker passes the application maximum, not the object's exact size.
        with adapter.open_bounded(key, size if operation == "exact_limit" else 5000000) as source:
            if operation == "read_all":
                assert source.read() == payload
            else:
                chunks = []
                while data := source.read(CHUNK_SIZE):
                    chunks.append(data)
                assert b"".join(chunks) == payload
            calls = len(body.timeout_calls)
            reads = len(body.read_calls)
            assert source.read(CHUNK_SIZE) == source.read() == b""
            assert len(body.timeout_calls) == calls
            assert len(body.read_calls) == reads
    assert body.timeout_calls and all(not released and 0 < timeout <= 2 for _, released, timeout in body.timeout_calls)
    assert body.eof_reads == 1  # An actual SDK EOF probe still runs once.
    assert all(0 < count <= CHUNK_SIZE for count in body.read_calls)
    assert body.closed_by_adapter and body._raw_stream.closed


@pytest.mark.parametrize("payload", [b"", b"truncated fictional bytes"])
def test_real_truncated_http_body_is_sanitized_and_closed(http_object, payload):
    response = http_object(payload, declared_length=len(payload) + 7)
    with pytest.raises(StorageUnavailable) as error:
        adapter_response(response).stat(new_key(uuid4(), uuid4()))
    assert str(error.value) == ""
    assert response["Body"].closed_by_adapter and response["Body"]._raw_stream.closed


def test_real_stalled_body_obeys_remaining_deadline_and_closes(http_object, monkeypatch):
    # Actual socket timeout, with the configured operation deadline shortened
    # only for this controlled test. The server releases on fixture teardown.
    monkeypatch.setattr("app.storage.s3.STORAGE_TIMEOUT", 0.1)
    response = http_object(b"partial", declared_length=100, hold_open=True)
    started = time.monotonic()
    with pytest.raises(StorageUnavailable) as error:
        adapter_response(response).stat(new_key(uuid4(), uuid4()))
    assert time.monotonic() - started < 1  # Server would otherwise wait 3 seconds.
    assert str(error.value) == ""
    assert response["Body"].timeout_calls and all(0 < timeout <= 0.1 for _, _, timeout in response["Body"].timeout_calls)
    assert response["Body"].closed_by_adapter and response["Body"]._raw_stream.closed


def test_zero_and_single_byte_reads_preserve_eof_and_timeout_lifecycle(http_object):
    payload = b"fictional small response"
    response = http_object(payload)
    body = response["Body"]
    with adapter_response(response).open_bounded(new_key(uuid4(), uuid4()), len(payload)) as source:
        assert source.read(0) == b"" and body.read_calls == []
        assert b"".join(source.read(1) for _ in payload) == payload
        assert body._raw_stream._fp.fp is None
        assert source.read(1) == b""
        assert body.eof_reads == 1
    assert all(not released and 0 < timeout <= 2 for _, released, timeout in body.timeout_calls)
    assert body.closed_by_adapter and body._raw_stream.closed


def test_real_oversized_body_is_closed_before_reading(http_object):
    response = http_object(b"four")
    with pytest.raises(StorageIntegrity):
        with adapter_response(response).open_bounded(new_key(uuid4(), uuid4()), 3):
            pytest.fail("Oversized response was opened")
    assert response["Body"].read_calls == []
    assert response["Body"].closed_by_adapter and response["Body"]._raw_stream.closed


@pytest.mark.parametrize("correct_digest", [True, False])
def test_worker_validates_real_http_bytes_or_reports_integrity_failure(http_object, tmp_path, monkeypatch, correct_digest):
    monkeypatch.setenv("DOCUMENT_TEMP_ROOT", str(tmp_path))
    payload, identity = pdf(), uuid4()
    response = http_object(payload)
    attempt = SimpleNamespace(storage_key=new_key(uuid4(), identity), byte_size=len(payload),
                              sha256=hashlib.sha256(payload if correct_digest else b"different").hexdigest())

    class Jobs:
        completed = None

        def claim(self, document_id):
            assert document_id == identity
            return attempt

        def complete(self, claimed, **result):
            assert claimed is attempt
            self.completed = result

    jobs = Jobs()
    process_document(identity, jobs=jobs, storage=adapter_response(response))
    assert jobs.completed == ({"state": "accepted", "detected_type": "pdf"} if correct_digest else {"state": "failed", "code": "storage_integrity"})
    assert response["Body"].closed_by_adapter and response["Body"]._raw_stream.closed
    assert list(tmp_path.iterdir()) == []
