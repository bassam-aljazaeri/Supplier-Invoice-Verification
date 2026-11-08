"""Signed API requests + real guarded PostgreSQL + disposable private storage."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
from threading import Barrier, Event
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import create_app
from app.models import Document, DocumentJob, Invoice, Workspace
from app.services import documents as service
from app.services.identity import ensure_application_user
from app.services.memberships import ensure_membership
from app.storage import StorageUnavailable
from app.storage.local import LocalDocumentStorage
from scripts.check_schema import require_test_marker
from tests.auth_helpers import SETTINGS
from tests.document_helpers import jpeg, multipart, pdf, png, upload_headers

pytestmark = pytest.mark.postgres


def auth(keys, subject, workspace):
    return {"Authorization": "Bearer " + keys.token(subject), "X-Workspace-ID": str(workspace)}


def upload(client, key=None, data=None, *, filename="fictional.pdf", headers=None):
    return client.post("/documents", content=multipart(data, filename), headers={**upload_headers(key or uuid4()), **(headers or {})})


@pytest.fixture
def document_api(schema_session, api_client, signing_keys, tmp_path):
    workspaces = [Workspace(slug=f"document-api-{index}", name=f"Fictional document company {index}") for index in range(2)]
    schema_session.add_all(workspaces)
    schema_session.flush()
    users = {}
    headers = {}
    for subject, role in [("doc-admin", "administrator"), ("doc-accountant", "accountant"), ("doc-approver", "approver"), ("doc-outsider", "administrator")]:
        user = ensure_application_user(schema_session, SETTINGS.issuer, subject)
        users[subject] = user.id
        workspace = workspaces[1] if subject == "doc-outsider" else workspaces[0]
        ensure_membership(schema_session, workspace.id, user.id, role)
        headers[subject] = auth(signing_keys, subject, workspace.id)
    schema_session.commit()
    api_client.headers.clear()
    api_client.headers.update(headers["doc-admin"])
    storage = LocalDocumentStorage(tmp_path / "private")
    api_client.app.state.documents.storage = storage
    api_client.app.state.documents.temp_dir = tmp_path / "incoming"
    return api_client, storage, workspaces, users, headers


@pytest.mark.parametrize("data", [pdf(), jpeg(), png()])
@pytest.mark.parametrize("role", ["doc-admin", "doc-accountant"])
def test_upload_original_bytes_queued_document_and_one_durable_job(document_api, schema_session, data, role):
    client, storage, workspaces, users, headers = document_api
    response = upload(client, data=data, filename="fictional.misleading-extension", headers=headers[role])
    assert response.status_code == 202, response.text
    saved = response.json()
    assert saved["state"] == "queued" and saved["detected_type"] is None and saved["error_code"] is None
    assert saved["uploader_id"] == str(users[role]) and saved["workspace_id"] == str(workspaces[0].id)
    assert set(saved) == {"id", "workspace_id", "uploader_id", "original_filename", "byte_size", "detected_type", "state", "error_code", "can_retry", "created_at", "updated_at", "uploaded_at", "finished_at"}
    assert response.headers["location"] == "/documents/" + saved["id"]
    assert response.headers["retry-after"] == "3" and response.headers["cache-control"] == "no-store"
    document = schema_session.get(Document, UUID(saved["id"]))
    assert document.sha256 == hashlib.sha256(data).hexdigest()
    assert document.upload_token is None and document.upload_lease_until is None
    with storage.open_bounded(document.storage_key, 5000000) as file:
        assert file.read() == data
    job = schema_session.get(DocumentJob, document.id)
    assert job.workspace_id == document.workspace_id and job.dispatch_state == "pending"
    assert job.attempt_count == job.manual_retry_count == 0
    assert job.next_attempt_at is not None and job.next_dispatch_at is not None
    assert schema_session.scalar(select(func.count()).select_from(DocumentJob)) == 1
    assert schema_session.scalar(select(func.count()).select_from(Invoice)) == 0
    assert not list((storage.root / "partials").iterdir())
    assert not list(client.app.state.documents.temp_dir.iterdir())


@pytest.mark.parametrize("role", ["doc-approver", "doc-outsider"])
def test_upload_write_permission_before_multipart_validation(document_api, role):
    client, _, workspaces, _, headers = document_api
    selected = {**headers[role], "X-Workspace-ID": str(workspaces[0].id), "X-Role": "administrator"}
    response = client.post("/documents", content=b"malformed", headers=selected)
    assert response.status_code == 403


@pytest.mark.parametrize("token", [None, "forged-token"])
def test_authentication_precedes_body_consumption(document_api, token):
    client = document_api[0]
    consumed = []
    async def exercise():
        async def body():
            consumed.append(True)
            yield b"malformed"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="http://test") as api:
            response = await api.post("/documents", content=body(), headers={**({"Authorization": "Bearer " + token} if token else {}), "Content-Length": "999999999"})
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"
    asyncio.run(exercise())
    assert consumed == []


def test_reads_pagination_filters_and_cross_workspace_metadata(document_api, schema_session):
    client, _, workspaces, _, headers = document_api
    keys = [uuid4() for _ in range(3)]
    ids = [upload(client, key).json()["id"] for key in keys]
    page = client.get("/documents?limit=1&offset=1").json()
    ordered = schema_session.scalars(select(Document.id).order_by(Document.created_at.desc(), Document.id.desc())).all()
    assert page["total"] == 3 and page["items"][0]["id"] == str(ordered[1])
    assert client.get("/documents?state=queued").json()["total"] == 3
    assert client.get("/documents?state=accepted").json()["total"] == 0
    for role in ("doc-admin", "doc-accountant", "doc-approver"):
        response = client.get("/documents/" + ids[0], headers=headers[role])
        assert response.status_code == 200 and "storage_key" not in response.text
    recovered = client.get("/documents?upload_attempt_key=" + str(keys[0])).json()
    assert recovered["total"] == 1 and recovered["items"][0]["id"] == ids[0]
    assert client.get("/documents?upload_attempt_key=" + str(keys[0]), headers=headers["doc-accountant"]).json()["total"] == 0
    assert client.get("/documents", headers=headers["doc-outsider"]).json()["total"] == 0
    assert client.get("/documents/" + ids[0], headers=headers["doc-outsider"]).status_code == 404
    assert client.get("/documents", headers={**headers["doc-outsider"], "X-Workspace-ID": str(workspaces[0].id)}).status_code == 403


@pytest.mark.parametrize("query", ["limit=0", "offset=10001", "state=unknown", "limit=1&limit=2", "workspace_id=x", "storage_key=x", "upload_attempt_key=bad"])
def test_document_query_validation_is_safe(document_api, query):
    response = document_api[0].get("/documents?" + query)
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"


def terminal(session, document_id, state="accepted", error=None):
    document = session.get(Document, UUID(document_id))
    now = session.scalar(select(func.clock_timestamp()))
    document.state, document.detected_type, document.finished_at = state, "pdf" if state == "accepted" else None, now - timedelta(seconds=61)
    document.error_code = error
    job = session.get(DocumentJob, document.id)
    job.dispatch_state, job.next_attempt_at, job.next_dispatch_at = "inactive", None, None
    job.attempt_count = 3 if state == "failed" else 1
    session.commit()
    return document, job


def test_replay_conflicts_terminal_replay_and_caller_scope(document_api, schema_session, monkeypatch):
    client, storage, _, _, headers = document_api
    calls, original = [], storage.put_new
    def count(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(storage, "put_new", count)
    key = uuid4()
    first = upload(client, key)
    replay = upload(client, key)
    assert replay.status_code == 202 and replay.json() == first.json()
    assert upload(client, key, pdf() + b"\n").status_code == 409
    assert upload(client, key, filename="renamed.pdf").status_code == 409
    terminal(schema_session, first.json()["id"])
    complete = upload(client, key)
    assert complete.status_code == 200 and complete.json()["state"] == "accepted"
    other = upload(client, key, headers=headers["doc-accountant"])
    assert other.status_code == 202 and other.json()["id"] != first.json()["id"]
    assert len(calls) == 2
    assert schema_session.scalar(select(func.count()).select_from(DocumentJob)) == 2


@pytest.mark.parametrize("value", [None, "bad", " " + str(uuid4()), str(uuid4()).upper(), "x,y"])
def test_upload_attempt_header_validation(document_api, value):
    response = document_api[0].post("/documents", content=multipart(), headers=upload_headers(value))
    assert response.status_code == 422


def test_other_endpoints_reject_write_headers_bodies_and_overrides(document_api):
    client = document_api[0]
    identifier = upload(client).json()["id"]
    assert client.get("/documents", headers={"Idempotency-Key": str(uuid4())}).status_code == 422
    assert client.post(f"/documents/{identifier}/download-url", json={"storage_key": "fictional"}).status_code == 422
    assert client.post(f"/documents/{identifier}/retry", content=b"{}").status_code == 422
    assert client.post(f"/documents/{identifier}/retry?workspace_id=x").status_code == 422
    assert client.get("/var/lib/supplier-invoice-verification/documents/objects/fictional").status_code == 404


@pytest.mark.parametrize(("content", "status"), [(multipart(b"PK\x03\x04fictional"), 415), (multipart(close=False), 422), (multipart(field="workspace_id"), 422), (multipart(b""), 422), (multipart(extra_headers=b"X-H: " + b"x" * 9000 + b"\r\n"), 422)])
def test_invalid_multipart_creates_no_records(document_api, schema_session, content, status):
    response = document_api[0].post("/documents", content=content, headers=upload_headers(uuid4()))
    assert response.status_code == status
    assert schema_session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.parametrize("length", [None, "1"])
def test_actual_api_body_bounds_without_trustworthy_length(document_api, schema_session, length):
    client = document_api[0]
    async def exercise():
        async def chunks():
            body = multipart(pdf() + b" " * 5000000)
            for index in range(0, len(body), 65536):
                yield body[index:index + 65536]
        headers = {**dict(client.headers), **upload_headers(uuid4())}
        if length is not None:
            headers["Content-Length"] = length
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="http://test") as api:
            response = await api.post("/documents", headers=headers, content=chunks())
        assert response.status_code == 413 and response.json()["error"]["code"] == "validation_error"
    asyncio.run(exercise())
    assert schema_session.scalar(select(func.count()).select_from(Document)) == 0
    exact = pdf() + b" " * (5000000 - len(pdf()))
    assert upload(client, data=exact).status_code == 202


@pytest.mark.parametrize("after_publication", [False, True])
def test_storage_failure_leaves_receiving_without_job_and_no_blind_delete(document_api, schema_session, monkeypatch, after_publication):
    client, storage, *_ = document_api
    original = storage.put_new
    def fail(*args):
        if after_publication:
            original(*args)
        raise StorageUnavailable("fictional-private-diagnostic")
    monkeypatch.setattr(storage, "put_new", fail)
    key = uuid4()
    response = upload(client, key)
    assert response.status_code == 503 and "fictional-private" not in response.text
    document = schema_session.scalar(select(Document))
    assert document.state == "receiving" and document.upload_token is not None
    assert schema_session.scalar(select(func.count()).select_from(DocumentJob)) == 0
    assert upload(client, key).json()["state"] == "receiving"
    if after_publication:
        assert storage.stat(document.storage_key).sha256 == document.sha256


@pytest.mark.parametrize("commit_number", [1, 2])
@pytest.mark.parametrize("after_commit", [False, True])
def test_database_commit_failure_and_uncertain_commit_preserve_consistency(document_api, schema_session, monkeypatch, commit_number, after_commit):
    client, storage, *_ = document_api
    original, calls = Session.commit, []
    def fail(session):
        calls.append(True)
        if len(calls) == commit_number:
            if after_commit:
                original(session)
            raise OperationalError("fictional-private-diagnostic", {}, Exception("fictional"))
        return original(session)
    monkeypatch.setattr(Session, "commit", fail)
    response = upload(client)
    assert response.status_code == 503 and "fictional-private" not in response.text
    document = schema_session.scalar(select(Document))
    jobs = schema_session.scalar(select(func.count()).select_from(DocumentJob))
    if commit_number == 1 and not after_commit:
        assert document is None and jobs == 0
    else:
        assert document.state == ("queued" if commit_number == 2 and after_commit else "receiving")
        assert jobs == (1 if commit_number == 2 and after_commit else 0)
        if commit_number == 2:
            assert storage.stat(document.storage_key).sha256 == document.sha256


def test_fenced_upload_owner_cannot_finalize_or_delete_object(document_api, schema_session, monkeypatch):
    client, storage, *_ = document_api
    original = storage.put_new
    owner = uuid4()
    def fence(*args):
        original(*args)
        document = schema_session.scalar(select(Document))
        document.upload_token = owner
        schema_session.commit()
    monkeypatch.setattr(storage, "put_new", fence)
    assert upload(client).status_code == 503
    schema_session.expire_all()
    document = schema_session.scalar(select(Document))
    assert document.state == "receiving" and document.upload_token == owner
    assert schema_session.scalar(select(func.count()).select_from(DocumentJob)) == 0
    assert storage.stat(document.storage_key).sha256 == document.sha256


@pytest.mark.parametrize("role", ["doc-admin", "doc-accountant", "doc-approver"])
def test_accepted_downloads_require_current_membership_and_safe_ticket(document_api, schema_session, role):
    client, _, _, _, headers = document_api
    identifier = upload(client).json()["id"]
    assert client.post(f"/documents/{identifier}/download-url", headers=headers[role]).status_code == 409
    terminal(schema_session, identifier)
    grant = client.post(f"/documents/{identifier}/download-url", headers=headers[role])
    assert grant.status_code == 200, grant.text
    path = grant.json()["url"].removeprefix("/api")
    download = client.get(path, headers=headers[role])
    assert download.status_code == 200 and download.content == pdf()
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["cache-control"] == "no-store"
    assert client.get(path + "!", headers=headers[role]).status_code == 403
    assert client.get(path, headers=headers["doc-outsider"]).status_code == 404
    from app.models import WorkspaceMembership
    user_id = document_api[3][role]
    schema_session.execute(delete(WorkspaceMembership).where(WorkspaceMembership.application_user_id == user_id))
    schema_session.commit()
    assert client.get(path, headers=headers[role]).status_code == 403


@pytest.mark.parametrize("role", ["doc-admin", "doc-accountant"])
def test_retry_is_explicit_eligible_and_limited_to_one_cycle(document_api, schema_session, role):
    client, _, _, _, headers = document_api
    client.headers.update(headers[role])
    identifier = upload(client).json()["id"]
    assert client.post(f"/documents/{identifier}/retry").status_code == 409
    _, job = terminal(schema_session, identifier, "failed", "processing_error")
    assert client.get(f"/documents/{identifier}").json()["can_retry"] is True
    assert client.get(f"/documents/{identifier}", headers=headers["doc-approver"]).json()["can_retry"] is False
    assert client.post(f"/documents/{identifier}/retry", headers=headers["doc-approver"]).status_code == 403
    assert client.post(f"/documents/{identifier}/retry").status_code == 202
    schema_session.refresh(job)
    assert job.attempt_count == 3 and job.manual_retry_count == 1 and job.dispatch_state == "pending"
    assert client.post(f"/documents/{identifier}/retry").status_code == 409


@pytest.mark.parametrize("reason", ["cooldown", "exhausted", "rejected", "integrity", "missing-bytes", "owned-attempt"])
def test_retry_eligibility_rejects_unsafe_worker_states(document_api, schema_session, reason):
    client, storage, *_ = document_api
    identifier = upload(client).json()["id"]
    document, job = terminal(schema_session, identifier, "failed", "processing_error")
    if reason == "cooldown":
        document.finished_at = schema_session.scalar(select(func.clock_timestamp()))
    elif reason == "exhausted":
        job.manual_retry_count, job.attempt_count = 1, 6
    elif reason == "rejected":
        document.state, document.error_code = "rejected", "invalid_file"
    elif reason == "integrity":
        document.error_code = "storage_integrity"
    elif reason == "missing-bytes":
        storage.delete(document.storage_key)
    else:
        job.attempt_token, job.processing_lease_until = uuid4(), schema_session.scalar(select(func.clock_timestamp())) + timedelta(seconds=120)
    schema_session.commit()
    result = client.post(f"/documents/{identifier}/retry")
    assert result.status_code == (503 if reason == "missing-bytes" else 409)
    schema_session.refresh(job)
    assert job.dispatch_state == "inactive"


def test_upload_capacity_is_bounded_and_recovers(document_api):
    client = document_api[0]
    slots = client.app.state.documents.slots
    for _ in range(4):
        assert slots.acquire(blocking=False)
    try:
        assert upload(client).status_code == 503
    finally:
        for _ in range(4):
            slots.release()
    assert upload(client).status_code == 202


@pytest.fixture
def concurrent_documents(postgres_engine, committed_memberships, signing_keys, tmp_path):
    import os
    records = committed_memberships
    app = create_app(verifier=signing_keys.verifier(), document_storage=LocalDocumentStorage(tmp_path / "private"), document_temp_dir=tmp_path / "incoming")
    def session_factory():
        with Session(postgres_engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                session.rollback()
                raise
    app.dependency_overrides[get_session] = session_factory
    try:
        with TestClient(app) as client:
            client.headers.update(auth(signing_keys, records["subjects"][0], records["workspace_id"]))
            yield client, app.state.documents.storage, records
    finally:
        with postgres_engine.begin() as connection:
            require_test_marker(connection, os.environ)
            connection.execute(delete(DocumentJob).where(DocumentJob.workspace_id == records["workspace_id"]))
            connection.execute(delete(Document).where(Document.workspace_id == records["workspace_id"]))


def test_concurrent_same_key_requests_have_one_document_object_and_job(concurrent_documents, postgres_engine, monkeypatch):
    client, storage, records = concurrent_documents
    barrier, original = Barrier(2), service.reserve_upload
    def simultaneously(*args):
        barrier.wait(timeout=5)
        return original(*args)
    monkeypatch.setattr(service, "reserve_upload", simultaneously)
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: upload(client, key), range(2)))
    assert all(response.status_code == 202 for response in results)
    assert len({response.json()["id"] for response in results}) == 1
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == records["workspace_id"])) == 1
        assert session.scalar(select(func.count()).select_from(DocumentJob).where(DocumentJob.workspace_id == records["workspace_id"])) == 1
    assert len(list((storage.root / "objects").iterdir())) == 1


def test_receiving_replay_and_conflict_never_delete_winning_upload(concurrent_documents, monkeypatch):
    client, storage, _ = concurrent_documents
    entered, release, original = Event(), Event(), storage.put_new
    def gated(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(storage, "put_new", gated)
    key = uuid4()
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(upload, client, key)
        try:
            assert entered.wait(5)
            replay = upload(client, key)
            assert replay.status_code == 202 and replay.json()["state"] == "receiving"
            assert upload(client, key, pdf() + b"\n").status_code == 409
        finally:
            release.set()
        assert first.result().status_code == 202
    assert len(list((storage.root / "objects").iterdir())) == 1
