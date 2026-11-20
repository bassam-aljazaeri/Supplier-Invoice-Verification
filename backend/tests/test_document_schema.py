"""Document/job invariants on real guarded PostgreSQL; no files or AWS involved."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, insert, inspect, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import configure_mappers

from app.models import ApplicationUser, Document, DocumentJob, Workspace, WorkspaceMembership

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)
LEASE = NOW + timedelta(seconds=120)
REJECTIONS = (
    "invalid_file", "unsupported_type", "pdf_encrypted", "pdf_page_count",
    "image_frame_count", "image_dimensions", "parser_limit",
)
TRANSIENT = ("storage_unavailable", "processing_interrupted", "processing_error")


@pytest.fixture
def owners(schema_session):
    workspaces = [Workspace(slug=f"documents-{index}", name=f"Fictional workspace {index}") for index in range(2)]
    users = [ApplicationUser(issuer="https://fictional.invalid", subject=f"document-uploader-{index}") for index in range(2)]
    schema_session.add_all([*workspaces, *users])
    schema_session.flush()
    membership = WorkspaceMembership(workspace_id=workspaces[0].id, application_user_id=users[0].id, role="accountant")
    schema_session.add(membership)
    schema_session.commit()
    return {"workspace": workspaces[0], "other_workspace": workspaces[1], "user": users[0], "other_user": users[1], "membership": membership}


def document_values(owners, initial_state="receiving", **overrides):
    values = dict(
        workspace_id=owners["workspace"].id, uploader_id=owners["user"].id,
        upload_attempt_key=uuid4(), storage_key=f"fictional-documents/{uuid4()}",
        original_filename="fictional-invoice.pdf", byte_size=2048, sha256="a" * 64,
        state=initial_state,
    )
    if initial_state == "receiving":
        values.update(upload_token=uuid4(), upload_lease_until=LEASE)
    else:
        values.update(uploaded_at=NOW)
    if initial_state in {"accepted", "rejected", "failed"}:
        values["finished_at"] = NOW
    if initial_state == "accepted":
        values["detected_type"] = "pdf"
    if initial_state == "rejected":
        values["error_code"] = "invalid_file"
    if initial_state == "failed":
        values["error_code"] = "processing_error"
    values.update(overrides)
    return values


def save_document(session, owners, state="receiving", **overrides):
    document_id = session.scalar(insert(Document).values(**document_values(owners, state, **overrides)).returning(Document.id))
    return session.get(Document, document_id)


def job_values(document, **overrides):
    values = dict(document_id=document.id, workspace_id=document.workspace_id, dispatch_state="pending", next_dispatch_at=NOW, next_attempt_at=NOW)
    values.update(overrides)
    return values


@pytest.mark.parametrize(("state", "overrides"), [
    ("receiving", {}), ("queued", {}), ("processing", {}),
    *[("accepted", {"detected_type": kind}) for kind in ("pdf", "jpeg", "png")],
    *[("rejected", {"error_code": code}) for code in REJECTIONS],
    *[("failed", {"error_code": code}) for code in TRANSIENT],
    ("failed", {"error_code": "upload_incomplete", "uploaded_at": None}),
    ("failed", {"error_code": "storage_integrity", "uploaded_at": None}),
    ("failed", {"error_code": "storage_integrity"}),
])
def test_valid_document_outcomes_persist_without_creating_invoices(schema_session, owners, state, overrides):
    document = save_document(schema_session, owners, state, **overrides)
    schema_session.commit()
    schema_session.expire_all()
    persisted = schema_session.get(Document, document.id)
    assert persisted.state == state
    assert persisted.workspace is owners["workspace"] and persisted.uploader is owners["user"]
    assert isinstance(persisted.id, UUID)
    assert persisted.created_at.tzinfo is not None and persisted.updated_at.tzinfo is not None
    assert schema_session.scalar(select(func.count()).select_from(Document)) == 1
    from app.models import Invoice
    assert schema_session.scalar(select(func.count()).select_from(Invoice)) == 0


def test_server_defaults_and_unicode_display_name(schema_session, owners):
    values = document_values(owners, original_filename="فاتورة fictive.png", byte_size=1)
    del values["state"]
    document_id = schema_session.scalar(insert(Document.__table__).values(**values).returning(Document.id))
    document = schema_session.get(Document, document_id)
    assert document.state == "receiving" and document.original_filename == "فاتورة fictive.png"
    assert document.created_at == document.updated_at
    queued = save_document(schema_session, owners, "queued", byte_size=5000000)
    schema_session.execute(insert(DocumentJob.__table__).values(**job_values(queued)))
    schema_session.commit()
    job = schema_session.get(DocumentJob, queued.id)
    assert job.attempt_count == job.manual_retry_count == 0
    assert job.created_at == job.updated_at and job.created_at.tzinfo is not None


@pytest.mark.parametrize(("state", "overrides"), [
    ("receiving", {"workspace_id": None}), ("receiving", {"uploader_id": None}),
    ("receiving", {"upload_attempt_key": None}), ("receiving", {"storage_key": None}),
    ("receiving", {"original_filename": None}), ("receiving", {"byte_size": None}),
    ("receiving", {"sha256": None}), ("receiving", {"state": None}),
    ("receiving", {"created_at": None}), ("receiving", {"updated_at": None}),
    ("receiving", {"workspace_id": uuid4()}), ("receiving", {"uploader_id": uuid4()}),
    *[("receiving", {"storage_key": value}) for value in ("", " ", " leading", "trailing ", "x" * 513)],
    *[("receiving", {"original_filename": value}) for value in ("", " \t", "../file.pdf", "C:\\file.pdf", "a\n.pdf", ".", "..", "x" * 256)],
    *[("receiving", {"byte_size": value}) for value in (-1, 0, 5000001)],
    *[("receiving", {"sha256": value}) for value in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64)],
    ("receiving", {"detected_type": "gif"}), ("receiving", {"state": "invented"}),
    ("receiving", {"upload_token": None}), ("receiving", {"upload_lease_until": None}),
    ("receiving", {"uploaded_at": NOW}), ("receiving", {"finished_at": NOW}),
    ("receiving", {"error_code": "invalid_file"}),
    ("queued", {"upload_token": uuid4(), "upload_lease_until": LEASE}),
    ("queued", {"upload_token": uuid4()}), ("queued", {"upload_lease_until": LEASE}),
    ("queued", {"uploaded_at": None}), ("queued", {"finished_at": NOW}),
    ("processing", {"error_code": "processing_error"}),
    ("accepted", {"detected_type": None}), ("accepted", {"finished_at": None}),
    ("accepted", {"error_code": "invalid_file"}),
    ("rejected", {"error_code": None}), ("rejected", {"error_code": "storage_unavailable"}),
    ("rejected", {"error_code": "raw-parser-diagnostic"}), ("rejected", {"finished_at": None}),
    ("failed", {"error_code": None}), ("failed", {"error_code": "invalid_file"}),
    ("failed", {"uploaded_at": None}), ("failed", {"finished_at": None}),
    ("failed", {"error_code": "upload_incomplete", "uploaded_at": NOW}),
])
def test_database_rejects_invalid_document_rows_and_session_recovers(schema_session, owners, state, overrides):
    with pytest.raises(DBAPIError), schema_session.begin_nested():
        schema_session.execute(insert(Document.__table__).values(**document_values(owners, state, **overrides)))
    assert save_document(schema_session, owners).id is not None


def test_upload_attempt_scope_and_identical_bytes_are_not_global_duplicates(schema_session, owners):
    key = uuid4()
    first = save_document(schema_session, owners, upload_attempt_key=key)
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        save_document(schema_session, owners, upload_attempt_key=key, sha256="b" * 64)
    assert failure.value.orig.diag.constraint_name == "uq_documents_upload_attempt"
    second = save_document(schema_session, owners, upload_attempt_key=key, uploader_id=owners["other_user"].id)
    third = save_document(schema_session, owners, upload_attempt_key=key, workspace_id=owners["other_workspace"].id)
    fourth = save_document(schema_session, owners)
    schema_session.commit()
    assert len({first.id, second.id, third.id, fourth.id}) == 4
    assert schema_session.scalar(select(func.count()).select_from(Document).where(Document.sha256 == "a" * 64)) == 4


def test_storage_keys_are_unique_and_not_silently_replaced(schema_session, owners):
    document = save_document(schema_session, owners)
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        save_document(schema_session, owners, storage_key=document.storage_key)
    assert failure.value.orig.diag.constraint_name == "uq_documents_storage_key"


INACTIVE = {"dispatch_state": "inactive", "next_dispatch_at": None, "next_attempt_at": None}
RUNNING = {**INACTIVE, "attempt_count": 1, "attempt_token": uuid4(), "processing_lease_until": LEASE}


@pytest.mark.parametrize("overrides", [
    {}, {"dispatch_state": "publishing", "dispatch_token": uuid4(), "dispatch_lease_until": LEASE},
    {"dispatch_state": "published", "last_published_at": NOW},
    RUNNING, {**INACTIVE, "attempt_count": 1}, {**INACTIVE, "attempt_count": 3},
    {"manual_retry_count": 1, "attempt_count": 3},
    {**RUNNING, "manual_retry_count": 1, "attempt_count": 4},
    {**INACTIVE, "manual_retry_count": 1, "attempt_count": 6},
    {**RUNNING, "manual_retry_count": 1, "attempt_count": 6},
])
def test_valid_job_schedules_and_budgets(schema_session, owners, overrides):
    state = "processing" if "attempt_token" in overrides else "accepted" if overrides.get("dispatch_state") == "inactive" else "queued"
    document = save_document(schema_session, owners, state)
    schema_session.execute(insert(DocumentJob).values(**job_values(document, **overrides)))
    schema_session.commit()
    schema_session.expire_all()
    job = schema_session.get(DocumentJob, document.id)
    assert job.document is document and document.job is job
    assert job.workspace is owners["workspace"]
    assert job.dispatch_state == overrides.get("dispatch_state", "pending")
    assert job.attempt_count == overrides.get("attempt_count", 0)


@pytest.mark.parametrize("overrides", [
    {"document_id": None}, {"workspace_id": None}, {"document_id": uuid4()},
    {"dispatch_state": None}, {"dispatch_state": "unknown"},
    {"attempt_count": None}, {"manual_retry_count": None}, {"created_at": None}, {"updated_at": None},
    {"attempt_count": -1}, {"attempt_count": 7}, {"manual_retry_count": -1}, {"manual_retry_count": 2},
    {**INACTIVE, "attempt_count": 4}, {**INACTIVE, "manual_retry_count": 1, "attempt_count": 2},
    {"attempt_count": 3}, {"manual_retry_count": 1, "attempt_count": 6},
    {"next_dispatch_at": None}, {"next_attempt_at": None},
    {**INACTIVE, "next_dispatch_at": NOW}, {**INACTIVE, "next_attempt_at": NOW},
    {"dispatch_state": "publishing"},
    {"dispatch_state": "publishing", "dispatch_token": uuid4()},
    {"dispatch_state": "publishing", "dispatch_lease_until": LEASE},
    {"dispatch_token": uuid4()}, {"dispatch_lease_until": LEASE},
    {"dispatch_state": "published"},
    {**INACTIVE, "attempt_count": 1, "attempt_token": uuid4()},
    {**INACTIVE, "attempt_count": 1, "processing_lease_until": LEASE},
    {**RUNNING, "attempt_count": 0},
    {"attempt_count": 1, "attempt_token": uuid4(), "processing_lease_until": LEASE},
])
def test_database_rejects_invalid_job_rows_and_session_recovers(schema_session, owners, overrides):
    document = save_document(schema_session, owners, "queued")
    with pytest.raises(IntegrityError), schema_session.begin_nested():
        schema_session.execute(insert(DocumentJob.__table__).values(**job_values(document, **overrides)))
    schema_session.execute(insert(DocumentJob).values(**job_values(document)))
    assert schema_session.get(DocumentJob, document.id) is not None


def test_job_workspace_and_single_job_constraints_on_insert_and_update(schema_session, owners):
    document = save_document(schema_session, owners, "queued")
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        schema_session.execute(insert(DocumentJob).values(**job_values(document, workspace_id=owners["other_workspace"].id)))
    assert failure.value.orig.diag.constraint_name == "fk_document_jobs_document"
    schema_session.execute(insert(DocumentJob).values(**job_values(document)))
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        schema_session.execute(update(DocumentJob).where(DocumentJob.document_id == document.id).values(workspace_id=owners["other_workspace"].id))
    assert failure.value.orig.diag.constraint_name == "fk_document_jobs_document"
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        schema_session.execute(insert(DocumentJob).values(**job_values(document)))
    assert failure.value.orig.diag.constraint_name == "pk_document_jobs"


def test_parent_relationship_does_not_overwrite_job_workspace(schema_session, owners):
    configure_mappers()
    document = save_document(schema_session, owners, "queued")
    with pytest.raises(IntegrityError), schema_session.begin_nested():
        job = DocumentJob(
            document=document, workspace_id=owners["other_workspace"].id,
            dispatch_state="pending", next_dispatch_at=NOW, next_attempt_at=NOW,
        )
        schema_session.add(job)
        schema_session.flush()


def test_membership_changes_preserve_document_uploader_history(schema_session, owners):
    document = save_document(schema_session, owners, "queued")
    schema_session.execute(insert(DocumentJob).values(**job_values(document)))
    document_id, user_id = document.id, owners["user"].id
    owners["membership"].role = "approver"
    schema_session.commit()
    schema_session.delete(owners["membership"])
    owners["user"].is_active = False
    schema_session.commit()
    schema_session.expire_all()
    assert schema_session.get(Document, document_id).uploader_id == user_id
    assert schema_session.get(DocumentJob, document_id).document.uploader.id == user_id
    assert schema_session.scalar(select(func.count()).select_from(WorkspaceMembership)) == 0
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        schema_session.execute(delete(ApplicationUser).where(ApplicationUser.id == user_id))
    assert failure.value.orig.diag.constraint_name == "fk_documents_uploader"
    with pytest.raises(IntegrityError) as failure, schema_session.begin_nested():
        schema_session.execute(delete(Document).where(Document.id == document_id))
    assert failure.value.orig.diag.constraint_name == "fk_document_jobs_document"


def test_document_job_insert_failure_rolls_back_both_and_allows_later_save(schema_session, owners):
    with pytest.raises(IntegrityError), schema_session.begin_nested():
        document = save_document(schema_session, owners, "queued")
        schema_session.execute(insert(DocumentJob).values(**job_values(document, workspace_id=owners["other_workspace"].id)))
    assert schema_session.scalar(select(func.count()).select_from(Document)) == 0
    assert schema_session.scalar(select(func.count()).select_from(DocumentJob)) == 0
    document = save_document(schema_session, owners, "queued")
    schema_session.execute(insert(DocumentJob).values(**job_values(document)))
    schema_session.commit()
    assert schema_session.get(DocumentJob, document.id).document.id == document.id


def test_expired_leases_remain_storable_for_later_reconciliation(schema_session, owners):
    expired = datetime(2000, 1, 1, tzinfo=timezone.utc)
    receiving = save_document(schema_session, owners, upload_lease_until=expired)
    processing = save_document(schema_session, owners, "processing")
    schema_session.execute(insert(DocumentJob).values(**job_values(processing, **{**RUNNING, "processing_lease_until": expired})))
    schema_session.commit()
    assert receiving.upload_lease_until == expired
    assert schema_session.get(DocumentJob, processing.id).processing_lease_until == expired


def test_document_indexes_and_foreign_keys_match_scoped_contract(postgres_engine):
    with postgres_engine.connect() as connection:
        inspector = inspect(connection)
        document_indexes = {item["name"]: item for item in inspector.get_indexes("documents")}
        assert document_indexes["ix_documents_workspace_created_id"]["column_names"] == ["workspace_id", "created_at", "id"]
        assert document_indexes["ix_documents_uploader"]["column_names"] == ["uploader_id"]
        assert "receiving" in document_indexes["ix_documents_receiving_lease"]["dialect_options"]["postgresql_where"]
        assert inspector.get_pk_constraint("document_jobs")["constrained_columns"] == ["document_id"]
        assert "id" not in DocumentJob.__table__.c
        constraints = {item["name"]: item for item in inspector.get_unique_constraints("documents")}
        assert constraints["uq_documents_upload_attempt"]["column_names"] == ["workspace_id", "uploader_id", "upload_attempt_key"]
        assert not any("sha256" in item["column_names"] for item in constraints.values())
        document_foreign_keys = inspector.get_foreign_keys("documents")
        assert {item["referred_table"] for item in document_foreign_keys} == {"workspaces", "application_users"}
        job_foreign_keys = {item["name"]: item for item in inspector.get_foreign_keys("document_jobs")}
        scoped = job_foreign_keys["fk_document_jobs_document"]
        assert scoped["constrained_columns"] == ["workspace_id", "document_id"]
        assert scoped["referred_columns"] == ["workspace_id", "id"]
        job_indexes = {item["name"]: item for item in inspector.get_indexes("document_jobs")}
        for name, column, predicate in [
            ("ix_document_jobs_due_dispatch", "next_dispatch_at", "pending"),
            ("ix_document_jobs_publishing_lease", "dispatch_lease_until", "publishing"),
            ("ix_document_jobs_processing_lease", "processing_lease_until", "IS NOT NULL"),
        ]:
            assert job_indexes[name]["column_names"][0] == column
            assert predicate in job_indexes[name]["dialect_options"]["postgresql_where"]
