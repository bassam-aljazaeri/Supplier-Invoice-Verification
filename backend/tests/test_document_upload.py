"""Raw ASGI stream tests: bounds apply during parsing, not after unrestricted form()."""

import asyncio
import hashlib

import pytest
from starlette.requests import Request

from app.api.errors import BusinessError
from app.document_upload import MAX_BODY_SIZE, receive_file, upload_boundary
from tests.document_helpers import jpeg, multipart, pdf, png, upload_headers


def request_for(chunks, headers=None):
    chunks = iter(chunks)
    async def receive():
        try:
            chunk = next(chunks)
            return {"type": "http.request", "body": chunk, "more_body": True}
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
    return Request({"type": "http", "method": "POST", "path": "/documents", "headers": [(name.lower().encode(), value.encode()) for name, value in (headers or upload_headers()).items()]}, receive)


@pytest.mark.parametrize("generate", [pdf, jpeg, png])
@pytest.mark.parametrize("tiny_chunks", [False, True])
def test_generated_formats_hash_original_bytes_and_strip_display_path(tmp_path, generate, tiny_chunks):
    data = generate()
    body = multipart(data, "C:\\fakepath\\fictional-file")
    chunks = [body[index:index + 1] for index in range(len(body))] if tiny_chunks else [body]
    request = request_for(chunks)
    received = asyncio.run(receive_file(request, upload_boundary(request), tmp_path))
    try:
        assert received.filename == "fictional-file"
        assert received.size == len(data) and received.sha256 == hashlib.sha256(data).hexdigest()
        assert received.file.read() == data
    finally:
        received.file.close()


@pytest.mark.parametrize(("body", "status"), [
    (multipart(b""), 422), (multipart(b"PK\x03\x04fictional ZIP"), 415),
    (multipart(close=False), 422), (multipart(field="workspace_id"), 422),
    (multipart(filename=".."), 422), (multipart(filename=" " * 4), 422),
    (multipart(filename="a" * 256), 422),
    (multipart(extra_headers=b"X-Fictional: " + b" " * 9000 + b"\r\n"), 422),
    (multipart(extra_headers=b"".join(f"X-{index}: x\r\n".encode() for index in range(17))), 422),
    (multipart(pdf() + b" " * 5000000), 413),
    (multipart() + b"x" * 65537, 413),
    (b"x" * (MAX_BODY_SIZE + 1), 413),
])
@pytest.mark.parametrize("length", [None, "1"])
def test_invalid_or_oversized_streams_close_resources_without_trusting_length(tmp_path, monkeypatch, body, status, length):
    from app import document_upload
    opened, original = [], document_upload.tempfile.TemporaryFile
    def track(**kwargs):
        file = original(**kwargs)
        opened.append(file)
        return file
    monkeypatch.setattr(document_upload.tempfile, "TemporaryFile", track)
    headers = upload_headers()
    if length is not None:
        headers["Content-Length"] = length
    request = request_for([body], headers)
    with pytest.raises(BusinessError) as failure:
        asyncio.run(receive_file(request, upload_boundary(request), tmp_path))
    assert failure.value.status == status
    assert opened and all(file.closed for file in opened)
    assert not list(tmp_path.iterdir())


def test_exact_file_boundary_and_early_stream_stop(tmp_path):
    data = pdf() + b" " * (5000000 - len(pdf()))
    request = request_for([multipart(data)])
    received = asyncio.run(receive_file(request, upload_boundary(request), tmp_path))
    assert received.size == 5000000
    received.file.close()
    reads = []
    async def exercise():
        body = multipart(data + b" ")
        async def receive():
            index = len(reads) * 65536
            reads.append(index)
            return {"type": "http.request", "body": body[index:index + 65536], "more_body": True}
        request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=fictional-boundary")]}, receive)
        with pytest.raises(BusinessError) as failure:
            await receive_file(request, upload_boundary(request), tmp_path)
        assert failure.value.status == 413
    asyncio.run(exercise())
    assert len(reads) < 100  # Reception stopped; it did not drain an unbounded source.


@pytest.mark.parametrize("disconnect", [False, True])
def test_idle_timeout_and_disconnect_are_safe(tmp_path, monkeypatch, disconnect):
    from app import document_upload
    monkeypatch.setattr(document_upload, "IDLE_TIMEOUT", 0.01)
    async def receive():
        if disconnect:
            return {"type": "http.disconnect"}
        await asyncio.sleep(1)
    request = Request({"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=fictional-boundary")]}, receive)
    with pytest.raises(BusinessError) as failure:
        asyncio.run(receive_file(request, upload_boundary(request), tmp_path))
    assert failure.value.status == 503 and not list(tmp_path.iterdir())
