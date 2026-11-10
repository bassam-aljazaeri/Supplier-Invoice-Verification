"""Small database-backed outbox dispatcher and bounded recovery loop."""

import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from sqlalchemy.exc import SQLAlchemyError

from app.document_runtime import DocumentRuntime
from app.services.document_jobs import Jobs
from app.storage import StorageError, StorageIntegrity, StorageMissing, StoredObject


def publish(document_id):
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for name in ("REDIS_HOST", "REDIS_PORT"):
        if name in os.environ:
            environment[name] = os.environ[name]
    process = subprocess.Popen(
        [sys.executable, "-m", "app.publish_document", str(document_id)],
        env=environment, cwd=str(Path(__file__).resolve().parents[1]),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, start_new_session=True,
    )
    try:
        try:
            return process.wait(timeout=10) == 0
        except subprocess.TimeoutExpired:
            return False
    finally:
        try:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            process.wait()


class Dispatcher:
    def __init__(self, jobs=None, storage=None, publisher=publish):
        self.jobs = jobs or Jobs()
        self.storage = storage or DocumentRuntime().get_storage()
        self.publisher = publisher

    def step(self):
        # Any DB error aborts this pass, including cleanup. No deletion on uncertainty.
        for identity in self.jobs.candidates("processing"):
            self.jobs.recover_processing(identity)
        for identity in self.jobs.candidates("uploads"):
            attempt = self.jobs.claim_upload(identity)
            if attempt is None:
                continue
            try:
                info = self.storage.stat(attempt.storage_key)
                result = "ready" if info == StoredObject(attempt.byte_size, attempt.sha256) else "integrity"
            except StorageMissing:
                result = "missing"
            except StorageIntegrity:
                result = "integrity"
            except StorageError:
                result = "unavailable"
            self.jobs.finish_upload(attempt, result)
        for identity in self.jobs.candidates("dispatch"):
            token = self.jobs.claim_dispatch(identity)
            if token is not None:
                try:
                    success = self.publisher(identity)  # No open database transaction.
                except Exception:
                    success = False
                self.jobs.finish_dispatch(identity, token, success)
        for candidate in self.storage.cleanup_candidates():
            threshold = time.time() - (600 if candidate.partial else 86400)
            if candidate.modified < threshold and (candidate.partial or self.jobs.may_delete(candidate.key)):
                self.storage.delete_candidate(candidate, threshold)


def main():
    stopped = threading.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    dispatcher = Dispatcher()
    try:
        while not stopped.is_set():
            try:
                dispatcher.step()
            except (SQLAlchemyError, StorageError, OSError):
                logging.warning("Document reconciliation deferred: infrastructure_unavailable")
            stopped.wait(5)
    finally:
        dispatcher.storage.close()


if __name__ == "__main__":
    main()
