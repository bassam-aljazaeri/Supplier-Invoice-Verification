"""Signed loopback HTTP + private-volume persistence, guarded disposable targets only."""

import argparse
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import create_database_engine
from app.models import Document, DocumentJob
from app.storage.local import LocalDocumentStorage
from scripts.check_auth import authentication_headers, require_disposable
from scripts.check_schema import approved_test_url, require_test_marker
from tests.document_helpers import multipart, png, upload_headers

SNAPSHOT = Path("/tmp/supplier-invoice-verification-documents.json")


def require(condition):
    if not condition:
        raise RuntimeError("Disposable document persistence verification failed.")


def request(method, path, body=None, headers=None):
    # Fixed loopback target; no CLI URL, redirect following, or remote credential use.
    connection = HTTPConnection("127.0.0.1", 8000, timeout=10)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        payload = response.read(65537)
        require(len(payload) <= 65536)
        return response.status, json.loads(payload)
    finally:
        connection.close()


def check(action):
    require_disposable()  # Before snapshot access, test keys, storage, or DB writes.
    require(os.environ.get("DOCUMENT_STORAGE_BACKEND") == "local")
    if action == "capture":
        key = str(uuid4())
        body = multipart(png(), "fictional-persistence.png")
        require(request("POST", "/documents", b"malformed")[0] == 401)
        status, document = request("POST", "/documents", body, {**authentication_headers(), **upload_headers(key)})
        require(status == 202 and document["state"] == "queued" and document["detected_type"] is None)
        replay_status, replay = request("POST", "/documents", body, {**authentication_headers(), **upload_headers(key)})
        require(replay_status == 202 and replay == document)
        require(request("POST", "/documents", multipart(png() + b"x", "fictional-persistence.png"), {**authentication_headers(), **upload_headers(key)})[0] == 409)
        snapshot = {"key": key, "document": document}
        SNAPSHOT.write_text(json.dumps(snapshot), encoding="utf-8")
        SNAPSHOT.chmod(0o600)
    else:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        document = snapshot["document"]
    status, saved = request("GET", "/documents/" + document["id"], headers=authentication_headers())
    require(status == 200 and saved == document)
    status, page = request("GET", "/documents?upload_attempt_key=" + snapshot["key"], headers=authentication_headers())
    require(status == 200 and page["total"] == 1 and page["items"] == [document])
    engine = create_database_engine(approved_test_url(os.environ))
    try:
        with Session(engine) as session:
            require_test_marker(session.connection(), os.environ)
            row = session.get(Document, UUID(document["id"]))
            jobs = session.scalars(select(DocumentJob).where(DocumentJob.document_id == row.id, DocumentJob.workspace_id == row.workspace_id)).all()
            require(row.state == "queued" and len(jobs) == 1 and jobs[0].dispatch_state == "pending")
            info = LocalDocumentStorage(os.environ["DOCUMENT_STORAGE_ROOT"]).stat(row.storage_key)
            require(info.byte_size == len(png()) and info.sha256 == hashlib.sha256(png()).hexdigest())
    finally:
        engine.dispose()
    print("Private document HTTP upload/replay/conflict, queued job, and stored-byte persistence verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "verify"])
    args = parser.parse_args()
    try:
        check(args.action)
        return 0
    except Exception:
        print("Disposable document check failed; internal details withheld.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
