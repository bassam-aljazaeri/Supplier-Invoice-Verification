"""Real Linux parser subprocess, limits and storage; no eager Celery or AWS."""

import hashlib
from io import BytesIO
import os
import subprocess
from uuid import uuid4

import pytest

from app.document_validation import check_containment, child, validate
from app.services.document_jobs import Attempt
from app.storage import StorageIntegrity
from app.storage.local import LocalDocumentStorage, new_key
from tests.document_helpers import jpeg, pdf as basic_pdf, png
from tests.processing_helpers import image, pdf


def run(tmp_path, monkeypatch, data):
    monkeypatch.setenv("DOCUMENT_TEMP_ROOT", str(tmp_path / "temp"))
    storage = LocalDocumentStorage(tmp_path / "storage")
    document, workspace = uuid4(), uuid4()
    key, digest = new_key(workspace, document), hashlib.sha256(data).hexdigest()
    storage.put_new(key, BytesIO(data), len(data), digest)
    attempt = Attempt(document, workspace, key, len(data), digest, uuid4())
    result = validate(storage, attempt)
    assert storage.stat(key).sha256 == digest
    assert list((tmp_path / "temp").iterdir()) == []
    return result


@pytest.mark.parametrize("data,expected", [
    (pdf(), {"state": "accepted", "detected_type": "pdf"}),
    (basic_pdf(), {"state": "accepted", "detected_type": "pdf"}),
    (png(), {"state": "accepted", "detected_type": "png"}),
    (jpeg(), {"state": "accepted", "detected_type": "jpeg"}),
    (image("JPEG"), {"state": "accepted", "detected_type": "jpeg"}),
    (b"%PDF-broken", {"state": "rejected", "code": "invalid_file"}),
    (pdf(2), {"state": "rejected", "code": "pdf_page_count"}),
    (pdf(0), {"state": "rejected", "code": "pdf_page_count"}),
    (pdf(encrypted=True), {"state": "rejected", "code": "pdf_encrypted"}),
    (b"\x89PNG\r\n\x1a\ninvalid", {"state": "rejected", "code": "invalid_file"}),
    (image(size=(10001, 1)), {"state": "rejected", "code": "image_dimensions"}),
    (image(size=(4000, 3000)), {"state": "rejected", "code": "image_dimensions"}),
    (image(size=(10000, 1)), {"state": "accepted", "detected_type": "png"}),
    (image(size=(4000, 2500)), {"state": "accepted", "detected_type": "png"}),
    (image(animated=True), {"state": "rejected", "code": "image_frame_count"}),
    (image("MPO", animated=True), {"state": "rejected", "code": "image_frame_count"}),
    (b"unsupported", {"state": "rejected", "code": "unsupported_type"}),
    (image()[:-15], {"state": "rejected", "code": "invalid_file"}),
])
def test_actual_parser(tmp_path, monkeypatch, data, expected):
    assert run(tmp_path, monkeypatch, data) == expected


def test_containment_and_scrubbed_credentials(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fictional-never-in-child")
    check_containment()


def test_wall_limit_kills_and_reaps_parser():
    assert child("probe", timeout=0.001) == {"state": "rejected", "code": "parser_limit"}


def test_parser_disappearing_during_cleanup_is_reaped(monkeypatch):
    original = os.killpg
    def disappeared(pid, sig):
        original(pid, sig)
        raise ProcessLookupError()
    monkeypatch.setattr(os, "killpg", disappeared)
    assert child("probe", timeout=0.001) == {"state": "rejected", "code": "parser_limit"}


def test_publisher_disappearing_during_timeout_cleanup_is_reaped(monkeypatch):
    from app.dispatch_documents import publish
    class Publisher:
        pid = 123
        reaped = False
        def poll(self):
            return None
        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("fictional-publisher", timeout)
            self.reaped = True
            return -9
    publisher = Publisher()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: publisher)
    def disappeared(*_):
        raise ProcessLookupError()
    monkeypatch.setattr(os, "killpg", disappeared)
    assert publish(uuid4()) is False
    assert publisher.reaped


def test_stored_integrity_verified_before_parser(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_TEMP_ROOT", str(tmp_path))
    storage = LocalDocumentStorage(tmp_path / "objects-root")
    doc, ws = uuid4(), uuid4()
    key, data = new_key(ws, doc), png()
    digest = hashlib.sha256(data).hexdigest()
    storage.put_new(key, BytesIO(data), len(data), digest)
    attempt = Attempt(doc, ws, key, len(data), "0" * 64, uuid4())
    with pytest.raises(StorageIntegrity):
        validate(storage, attempt)
