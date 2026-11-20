"""Disposable-only interruption gate around the real production Celery task."""

import os
import logging
from pathlib import Path
import time

from app.db import create_database_engine
from scripts.check_schema import approved_test_url, require_test_marker


def main():
    engine = create_database_engine(approved_test_url(os.environ))
    try:
        with engine.connect() as connection:
            require_test_marker(connection, os.environ)
    finally:
        engine.dispose()
    import app.document_tasks as tasks
    from celery.signals import task_prerun, task_postrun
    from app.document_worker import main as run_worker
    original = tasks.process_document
    root = Path(os.environ["DOCUMENT_STORAGE_ROOT"])

    @task_prerun.connect(weak=False)
    def started(task_id=None, **_):
        logging.warning("Disposable task started: %s", task_id)

    @task_postrun.connect(weak=False)
    def finished(task_id=None, **_):
        logging.warning("Disposable task finished: %s", task_id)

    def gate(identity):
        path = root / ".test-worker-gate"
        if path.exists() and path.read_text() == str(identity):
            (root / ".test-worker-claimed").write_text(str(identity))
            deadline = time.monotonic() + 40
            while path.exists() and time.monotonic() < deadline:
                time.sleep(0.1)

    def controlled(identity):
        return original(identity, after_claim=gate)

    tasks.process_document = controlled
    run_worker()


if __name__ == "__main__":
    main()
