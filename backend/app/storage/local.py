"""Linux private-volume storage: immutable publication, bounded reads, no paths from users."""

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import stat
import time
from uuid import UUID, uuid4

from app.storage import DownloadGrant, StorageError, StorageIntegrity, StorageMissing, StorageUnavailable, StoredObject

MAX_FILE_SIZE = 5000000
CHUNK_SIZE = 65536
STORAGE_TIMEOUT = 15
KEY_PATTERN = re.compile(r"d-[0-9a-f]{32}-[0-9a-f]{32}-[0-9a-f]{32}\Z")


def new_key(workspace_id: UUID, document_id: UUID) -> str:
    return f"d-{workspace_id.hex}-{document_id.hex}-{uuid4().hex}"


class BoundedReader:
    def __init__(self, file, maximum):
        self.file, self.remaining = file, maximum

    def read(self, size=-1):
        count = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        data = self.file.read(count)
        if len(data) > self.remaining:
            raise StorageIntegrity()
        self.remaining -= len(data)
        return data


class LocalDocumentStorage:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        if not self.root.is_absolute() or ".." in self.root.parts:
            raise StorageIntegrity()
        self._signing_key = secrets.token_bytes(32)

    @contextmanager
    def _directories(self):
        descriptors = []
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.root.resolve() != self.root:
                raise StorageIntegrity()
            root = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(root)
            os.fchmod(root, 0o700)
            for name in ("objects", "partials"):
                try:
                    os.mkdir(name, mode=0o700, dir_fd=root)
                except FileExistsError:
                    pass
                descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
                descriptors.append(descriptor)
                os.fchmod(descriptor, 0o700)
            yield descriptors[1], descriptors[2]
        except StorageError:
            raise
        except OSError:
            raise StorageUnavailable() from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
            raise StorageIntegrity()

    @contextmanager
    def open_bounded(self, key, max_bytes):
        self._key(key)
        if not 0 <= max_bytes <= MAX_FILE_SIZE:
            raise StorageIntegrity()
        with self._directories() as (objects, _):
            try:
                descriptor = os.open(key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=objects)
            except FileNotFoundError:
                raise StorageMissing() from None
            try:
                with os.fdopen(descriptor, "rb") as file:
                    info = os.fstat(file.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
                        raise StorageIntegrity()
                    yield BoundedReader(file, max_bytes)
            except StorageError:
                raise
            except OSError:
                raise StorageUnavailable() from None

    def stat(self, key):
        digest, size = hashlib.sha256(), 0
        with self.open_bounded(key, MAX_FILE_SIZE) as file:
            while data := file.read(CHUNK_SIZE):
                digest.update(data)
                size += len(data)
        return StoredObject(size, digest.hexdigest())

    def put_new(self, key, file, size, sha256):
        self._key(key)
        if not 1 <= size <= MAX_FILE_SIZE:
            raise StorageIntegrity()
        deadline = time.monotonic() + STORAGE_TIMEOUT

        def check_time():
            if time.monotonic() >= deadline:
                raise StorageUnavailable()

        with self._directories() as (objects, partials):
            partial = uuid4().hex + ".part"
            try:
                descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=partials)
                with os.fdopen(descriptor, "wb") as destination:
                    digest, actual = hashlib.sha256(), 0
                    file.seek(0)
                    while data := file.read(CHUNK_SIZE):
                        check_time()
                        actual += len(data)
                        if actual > size:
                            raise StorageIntegrity()
                        digest.update(data)
                        destination.write(data)
                    if actual != size or digest.hexdigest() != sha256:
                        raise StorageIntegrity()
                    destination.flush()
                    os.fsync(destination.fileno())
                check_time()
                try:
                    # link is atomic and exclusive; rename/replace could overwrite a winner.
                    os.link(partial, key, src_dir_fd=partials, dst_dir_fd=objects, follow_symlinks=False)
                    os.fsync(objects)
                except FileExistsError:
                    if self.stat(key) != StoredObject(size, sha256):
                        raise StorageIntegrity() from None
                check_time()
            finally:
                try:
                    os.unlink(partial, dir_fd=partials)
                except FileNotFoundError:
                    pass

    def delete(self, key):
        self._key(key)
        with self._directories() as (objects, _):
            try:
                os.unlink(key, dir_fd=objects)
                os.fsync(objects)
            except FileNotFoundError:
                pass

    def download_grant(self, document_id, workspace_id, caller_id, expires_in=60):
        if not 1 <= expires_in <= 60:
            raise StorageIntegrity()
        expiry = int(time.time()) + expires_in
        payload = f"{document_id}.{workspace_id}.{caller_id}.{expiry}.{uuid4().hex}".encode("ascii")
        encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
        signature = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return DownloadGrant(f"/api/documents/{document_id}/local-content?ticket={encoded}.{signature}", datetime.fromtimestamp(expiry, timezone.utc))

    def verify_ticket(self, ticket, document_id, workspace_id, caller_id):
        try:
            if len(ticket) > 512:
                return False
            encoded, signature = ticket.split(".")
            expected = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                return False
            payload = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True).decode("ascii")
            doc, workspace, caller, expiry, nonce = payload.split(".")
            return (doc, workspace, caller) == (str(document_id), str(workspace_id), str(caller_id)) and len(nonce) == 32 and int(expiry) > time.time()
        except (ValueError, UnicodeError, TypeError):
            return False
