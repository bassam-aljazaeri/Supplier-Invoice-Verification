"""Per-API upload capacity, lazy private storage, and bounded storage awaits."""

import asyncio
import os
from pathlib import Path
import threading

from app.api.errors import unavailable
from app.storage import StorageError, StoredObject
from app.storage.factory import configured_storage

STORAGE_WAIT = 15


class DocumentRuntime:
    def __init__(self, storage=None, temp_dir=None):
        self.storage = storage
        self.temp_dir = Path(temp_dir or os.getenv("DOCUMENT_TEMP_ROOT", "/tmp/siv-documents"))
        self.slots = threading.BoundedSemaphore(4)
        self.pending = set()
        self._lock = threading.Lock()

    def get_storage(self):
        with self._lock:
            if self.storage is None:
                try:
                    self.storage = configured_storage()
                except StorageError:
                    raise unavailable() from None
            return self.storage

    def track(self, task):
        self.pending.add(task)

        def completed(future):
            self.pending.discard(future)
            if not future.cancelled():
                future.exception()  # Consume late failures without logging input/paths.

        task.add_done_callback(completed)
        return task

    async def close(self):
        if self.pending:
            await asyncio.wait(tuple(self.pending), timeout=STORAGE_WAIT)


async def storage_call(operation, *args):
    try:
        return await asyncio.wait_for(asyncio.to_thread(operation, *args), STORAGE_WAIT)
    except (StorageError, OSError, TimeoutError):
        raise unavailable() from None


def verify_object(storage, key, size, sha256):
    if storage.stat(key) != StoredObject(size, sha256):
        from app.storage import StorageIntegrity
        raise StorageIntegrity()
