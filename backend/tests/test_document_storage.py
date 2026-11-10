"""Real private filesystem failure/containment tests, entirely disposable."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import os
import stat
from uuid import uuid4

import pytest

from app.storage import StorageError, StorageIntegrity, StorageMissing, StoredObject
from app.storage.local import LocalDocumentStorage, new_key
from tests.document_helpers import pdf, png


def put(storage, key, data):
    storage.put_new(key, BytesIO(data), len(data), hashlib.sha256(data).hexdigest())


def test_private_immutable_publication_and_bounded_read(tmp_path):
    storage = LocalDocumentStorage(tmp_path / "private")
    key, data = new_key(uuid4(), uuid4()), pdf()
    put(storage, key, data)
    put(storage, key, data)
    assert storage.stat(key) == StoredObject(len(data), hashlib.sha256(data).hexdigest())
    with storage.open_bounded(key, len(data)) as file:
        assert file.read() == data and file.read() == b""
    with pytest.raises(StorageIntegrity):
        with storage.open_bounded(key, len(data) - 1):
            pass
    assert list((storage.root / "partials").iterdir()) == []
    assert stat.S_IMODE((storage.root / "objects" / key).stat().st_mode) == 0o600
    assert stat.S_IMODE(storage.root.stat().st_mode) == 0o700
    storage.delete(key)
    storage.delete(key)
    with pytest.raises(StorageMissing):
        storage.stat(key)


@pytest.mark.parametrize("key", ["../outside", "/etc/passwd", "objects/../x", "x\\y", "", "filename.pdf"])
def test_paths_are_never_accepted_as_keys(tmp_path, key):
    storage = LocalDocumentStorage(tmp_path / "private")
    with pytest.raises(StorageIntegrity):
        put(storage, key, pdf())


@pytest.mark.parametrize("location", ["root", "objects", "object"])
def test_symlinks_cannot_escape_root(tmp_path, location):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "fictional-only"
    secret.write_bytes(b"fictional private bytes")
    root = tmp_path / "private"
    key = new_key(uuid4(), uuid4())
    if location == "root":
        root.symlink_to(outside, target_is_directory=True)
    else:
        root.mkdir()
        if location == "objects":
            (root / "objects").symlink_to(outside, target_is_directory=True)
        else:
            (root / "objects").mkdir()
            (root / "objects" / key).symlink_to(secret)
    with pytest.raises(StorageError):
        LocalDocumentStorage(root).stat(key)
    assert secret.read_bytes() == b"fictional private bytes"


def test_conflicting_concurrent_publications_do_not_replace_winner(tmp_path):
    storage, key = LocalDocumentStorage(tmp_path / "private"), new_key(uuid4(), uuid4())
    values = [pdf(), pdf() + b"\n"]
    def publish(value):
        try:
            put(storage, key, value)
            return True
        except StorageIntegrity:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(publish, values)) == [False, True]
    with storage.open_bounded(key, 5000000) as file:
        assert file.read() in values
    assert not list((storage.root / "partials").iterdir())


def test_partial_read_failure_is_cleaned_without_completed_object(tmp_path):
    class Broken(BytesIO):
        def read(self, *args):
            raise OSError("fictional-private-diagnostic")
    storage, key = LocalDocumentStorage(tmp_path / "private"), new_key(uuid4(), uuid4())
    with pytest.raises(StorageError):
        storage.put_new(key, Broken(pdf()), len(pdf()), hashlib.sha256(pdf()).hexdigest())
    assert not list((storage.root / "partials").iterdir())
    assert not list((storage.root / "objects").iterdir())


def test_failure_after_publication_keeps_completed_bytes(tmp_path, monkeypatch):
    storage, key = LocalDocumentStorage(tmp_path / "private"), new_key(uuid4(), uuid4())
    original = os.fsync
    def fail_directory(descriptor):
        original(descriptor)
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("fictional-private-diagnostic")
    monkeypatch.setattr(os, "fsync", fail_directory)
    with pytest.raises(StorageError):
        put(storage, key, pdf())
    assert storage.stat(key).sha256 == hashlib.sha256(pdf()).hexdigest()
    assert not list((storage.root / "partials").iterdir())


def test_ticket_scope_tampering_expiry_and_restart(tmp_path, monkeypatch):
    from app.storage import local
    monkeypatch.setattr(local.time, "time", lambda: 1000)
    storage = LocalDocumentStorage(tmp_path / "private")
    doc, workspace, caller = uuid4(), uuid4(), uuid4()
    ticket = storage.download_grant(doc, workspace, caller, 60).url.split("ticket=")[1]
    assert storage.verify_ticket(ticket, doc, workspace, caller)
    assert not storage.verify_ticket(ticket, uuid4(), workspace, caller)
    assert not storage.verify_ticket(ticket, doc, uuid4(), caller)
    assert not storage.verify_ticket(ticket, doc, workspace, uuid4())
    assert not storage.verify_ticket(ticket[:-1] + "!", doc, workspace, caller)
    assert not storage.verify_ticket("é.é", doc, workspace, caller)
    assert not LocalDocumentStorage(storage.root).verify_ticket(ticket, doc, workspace, caller)
    monkeypatch.setattr(local.time, "time", lambda: 1060)
    assert not storage.verify_ticket(ticket, doc, workspace, caller)


def test_cleanup_scan_is_bounded_and_advances_across_passes(tmp_path):
    storage = LocalDocumentStorage(tmp_path / "private")
    for _ in range(113):
        put(storage, new_key(uuid4(), uuid4()), png())
    seen = set()
    try:
        for _ in range(3):
            candidates = storage.cleanup_candidates()
            assert len(candidates) <= 100
            seen.update(c.key for c in candidates)
        assert len(seen) == 113
    finally:
        storage.close()
