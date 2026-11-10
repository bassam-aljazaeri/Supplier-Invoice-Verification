"""Real HTTP/Redis/worker verification. Only guarded disposable targets and fixtures.

The host checker stops/starts actual services between phases. Timestamp acceleration
avoids waiting lease/retry durations; focused PostgreSQL tests check those durations.
No eager mode, production test switch, AWS or external identity service is used.
"""

import argparse
import base64
from datetime import timedelta
import hashlib
from http.client import HTTPConnection
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid4

from redis import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.orm import sessionmaker

from app.celery_app import app as celery
from app.db import create_database_engine
from app.models import Document, DocumentJob
from app.services.document_jobs import Jobs
from app.storage.local import LocalDocumentStorage
from scripts.check_auth import authentication_headers, require_disposable
from scripts.check_documents import request
from scripts.check_schema import approved_test_url, require_test_marker
from tests.document_helpers import multipart, png, upload_headers
from tests.processing_helpers import image, pdf

SNAPSHOT = Path("/tmp/supplier-invoice-verification-processing.json")


class ProcessingCheckFailure(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("Disposable processing assertion failed.")


def require(condition, code="processing_invariant"):
    if not condition:
        raise ProcessingCheckFailure(code)


def failure_details(error):
    # Never format exceptions: SQL/HTTP/library messages can contain private input.
    details = {"check": error.code if isinstance(error, ProcessingCheckFailure) else "unexpected_exception",
               "exception_type": type(error).__name__}
    traceback = error.__traceback__
    while traceback is not None:
        code = traceback.tb_frame.f_code
        if code.co_filename == __file__ and code.co_name not in {"require", "wait"}:
            details["site"] = f"{code.co_name}:{traceback.tb_lineno}"
        traceback = traceback.tb_next
    return details


def wait(predicate, timeout=90, *, failure_code="processing_deadline"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.25)
    raise ProcessingCheckFailure(failure_code)


class Check:
    def __init__(self):
        require_disposable()
        self.engine = create_database_engine(approved_test_url(os.environ))
        with self.engine.connect() as c:
            require_test_marker(c, os.environ)
        self.jobs = Jobs(sessionmaker(self.engine, expire_on_commit=False))
        self.root = Path(os.environ["DOCUMENT_STORAGE_ROOT"])
        self.storage = LocalDocumentStorage(self.root)
        self.saved = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}

    def upload(self, label, data=None):
        data = png() if data is None else data
        status, d = request("POST", "/documents", multipart(data, "fictional-" + label), {**authentication_headers(), **upload_headers(str(uuid4()))})
        require(status == 202 and d["state"] == "queued", "upload_queued_response")
        self.saved[label] = d["id"]
        SNAPSHOT.write_text(json.dumps(self.saved))
        SNAPSHOT.chmod(0o600)
        with self.jobs.transaction() as s:
            j = s.get(DocumentJob, UUID(d["id"]))
            require(j is not None and j.attempt_count == 0, "upload_durable_unclaimed_job")
        return d

    def identity(self, label):
        return UUID(self.saved[label])

    def row(self, label):
        status, d = request("GET", "/documents/" + self.saved[label], headers=authentication_headers())
        require(status == 200)
        return d

    def terminal(self, label, state, code=None):
        d = wait(lambda: (d if (d := self.row(label))["state"] in ("accepted", "rejected", "failed") else None))
        require(d["state"] == state and d["error_code"] == code)
        return d

    def accelerate(self, label, processing=False):
        with self.jobs.transaction() as s:
            d, j = self.jobs.pair(s, self.identity(label))
            if d is None or j is None:
                return  # A real worker owns the row; do not turn contention into a test failure.
            now = self.jobs.clock(s)
            if processing:
                require(d.state == "processing")
                j.processing_lease_until = now - timedelta(seconds=1)
            elif d.state == "queued" and j.dispatch_state != "publishing":
                j.next_dispatch_at = j.next_attempt_at = now - timedelta(seconds=1)

    def run(self, phase):
        if phase == "prepare":
            for label, data in (("pdf", pdf()), ("jpeg", image("JPEG")), ("png", png()),
                                ("broken", b"%PDF-1.7\nbroken"), ("encrypted", pdf(encrypted=True)),
                                ("multipage", pdf(2)), ("dimensions", image(size=(10001, 1))),
                                ("invalid-image", b"\x89PNG\r\n\x1a\nbroken"), ("animation", image(animated=True))):
                d = self.upload(label, data)
                require(request("POST", "/documents/" + d["id"] + "/download-url", headers=authentication_headers())[0] == 409)
        elif phase == "validate":
            for label in ("pdf", "jpeg", "png"):
                self.terminal(label, "accepted")
            for label, code in (("broken", "invalid_file"), ("encrypted", "pdf_encrypted"), ("multipage", "pdf_page_count"), ("dimensions", "image_dimensions"), ("invalid-image", "invalid_file"), ("animation", "image_frame_count")):
                self.terminal(label, "rejected", code)
                require(request("POST", "/documents/" + self.saved[label] + "/download-url", headers=authentication_headers())[0] == 409)
            status, grant = request("POST", "/documents/" + self.saved["png"] + "/download-url", headers=authentication_headers())
            require(status == 200)
            connection = HTTPConnection("127.0.0.1", 8000, timeout=10)
            try:
                # The local adapter returns /api/... for the frontend proxy; direct API has no /api prefix.
                path = grant["url"].removeprefix("/api")
                connection.request("GET", path, headers=authentication_headers())
                response = connection.getresponse()
                require(response.status == 200 and response.read(5000001) == png())
                require(response.getheader("Content-Disposition").startswith("attachment"))
                connection.request("GET", path)
                response = connection.getresponse()
                require(response.status == 401)
                response.read()
            finally:
                connection.close()
            for _ in range(3):
                celery.send_task("documents.validate", kwargs={"document_id": self.saved["png"]}, retry=False)
            time.sleep(2)
            with self.jobs.transaction() as s:
                require(s.get(DocumentJob, self.identity("png")).attempt_count == 1)
        elif phase == "outage-upload":
            self.upload("outage")
            wait(lambda: self.publish_failed("outage"), failure_code="outage_publish_backoff_deadline")
        elif phase == "outage-recover":
            self.accelerate("outage")
            self.terminal("outage", "accepted")
        elif phase == "lose-message":
            self.upload("lost")
            wait(lambda: self.published("lost"))
            broker = Redis(host="redis", port=6379, db=1, socket_timeout=3, socket_connect_timeout=2)
            try:
                require(broker.llen("siv-documents:documents") > 0)
                message = json.loads(broker.lindex("siv-documents:documents", 0))
                arguments = json.loads(base64.b64decode(message["body"]))
                require(arguments[0] == [] and arguments[1] == {"document_id": self.saved["lost"]})
                broker.delete("siv-documents:documents")  # Only this guarded stack's broker queue.
            finally:
                broker.close()
            self.accelerate("lost")
        elif phase == "lost-recover":
            # Startup/claim can race a publication. Keep only this fixture's DB
            # scheduling eligible while waiting, rather than waiting a real 180s.
            def recovered():
                self.accelerate("lost")
                return self.row("lost")["state"] == "accepted"
            wait(recovered)
            self.terminal("lost", "accepted")
        elif phase == "arm-interruption":
            d = self.upload("interrupted")
            (self.root / ".test-worker-gate").write_text(d["id"])
        elif phase == "claimed":
            wait(lambda: (self.root / ".test-worker-claimed").exists())
            require(self.row("interrupted")["state"] == "processing")
        elif phase == "expire":
            self.accelerate("interrupted", processing=True)
            (self.root / ".test-worker-gate").unlink()
        elif phase == "interruption-recover":
            self.terminal("interrupted", "accepted")
            with self.jobs.transaction() as s:
                require(s.get(DocumentJob, self.identity("interrupted")).attempt_count == 2)
        elif phase == "arm-storage-failure":
            self.upload("missing")
            with self.jobs.transaction() as s:
                key = s.get(Document, self.identity("missing")).storage_key
            self.storage.delete(key)
        elif phase == "exhaust-retry":
            def exhausted():
                self.accelerate("missing")
                return self.row("missing")["state"] == "failed"
            wait(exhausted)
            self.terminal("missing", "failed", "storage_unavailable")
            with self.jobs.transaction() as s:
                d, j = self.jobs.pair(s, self.identity("missing"))
                require(j.attempt_count == 3)
                d.finished_at = self.jobs.clock(s) - timedelta(seconds=61)
                key = d.storage_key
            self.storage.put_new(key, BytesIO(png()), len(png()), hashlib.sha256(png()).hexdigest())
            require(request("POST", "/documents/" + self.saved["missing"] + "/retry", headers=authentication_headers())[0] == 202)
            self.terminal("missing", "accepted")
            with self.jobs.transaction() as s:
                j = s.get(DocumentJob, self.identity("missing"))
                require(j.attempt_count == 4 and j.manual_retry_count == 1)
        else:
            raise ValueError()
        print("Real HTTP/Redis/worker processing phase verified: " + phase)

    def published(self, label):
        with self.jobs.transaction() as s:
            row = self.observation(s, label)
            require(row is not None and row["dispatch"] is not None, "published_document_job_present")
            return row["dispatch"] == "published"

    def observation(self, session, label):
        # One coherent READ COMMITTED snapshot. Observers must not claim/lock rows:
        # SKIP LOCKED can omit them, and FOR UPDATE can obstruct publisher bookkeeping.
        return session.execute(select(
            Document.state.label("state"), Document.error_code.label("error_code"),
            DocumentJob.dispatch_state.label("dispatch"), DocumentJob.attempt_count.label("attempts"),
            DocumentJob.next_dispatch_at.label("next_dispatch_at"),
            DocumentJob.updated_at.label("dispatch_updated_at"), func.clock_timestamp().label("observed_at"),
        ).select_from(Document).outerjoin(DocumentJob, and_(
            DocumentJob.document_id == Document.id, DocumentJob.workspace_id == Document.workspace_id,
        )).where(Document.id == self.identity(label))).mappings().one_or_none()

    def publish_failed(self, label):
        with self.jobs.transaction() as s:
            row = self.observation(s, label)
            require(row is not None, "outage_document_present")
            require(row["dispatch"] is not None, "outage_job_present")
            require(row["state"] == "queued" and row["error_code"] is None, "outage_document_queued")
            require(row["attempts"] == 0, "outage_no_processing_attempt")
            require(row["dispatch"] in {"pending", "publishing"}, "outage_dispatch_pending_or_publishing")
            if row["dispatch"] != "pending" or row["next_dispatch_at"] <= row["observed_at"]:
                return False  # Initial due work or a normal in-flight bounded publish.
            require(row["next_dispatch_at"] - row["dispatch_updated_at"] == timedelta(seconds=30), "outage_publish_backoff_30_seconds")
            return True

    def diagnostics(self):
        # Only fixed fixture labels and safe state/counters; never keys, tokens or bytes.
        with self.jobs.transaction() as s:
            for label, identity in self.saved.items():
                row = self.observation(s, label)
                print(json.dumps({"fixture": label, **{key: None if row is None else row[key]
                                  for key in ("state", "error_code", "dispatch", "attempts")}}), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase")
    args = parser.parse_args()
    check = None
    try:
        check = Check()
        check.run(args.phase)
        return 0
    except Exception as error:
        print("Disposable background-processing verification failed in phase " + args.phase + "; details withheld.", file=sys.stderr)
        print(json.dumps(failure_details(error)), file=sys.stderr)
        if check is not None:
            try:
                check.diagnostics()
            except Exception:
                pass
        return 1
    finally:
        if check is not None:
            check.storage.close()
            check.engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
