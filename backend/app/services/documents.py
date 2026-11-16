"""Short explicit transactions. Storage I/O and parsing never hold database locks."""

from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from uuid import uuid4

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.api.errors import BusinessError, missing, unavailable
from app.models import Document, DocumentJob
from app.schemas.document import DocumentRead
from app.storage.keys import new_key

RETRYABLE = {"storage_unavailable", "processing_interrupted", "processing_error"}
WRITERS = {"administrator", "accountant"}
TERMINAL = {"accepted", "rejected", "failed"}


def rollback(session):
    try:
        session.rollback()
    except SQLAlchemyError:
        session.close()


def database_operation(operation):
    @wraps(operation)
    def wrapped(session, *args, **kwargs):
        try:
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            return operation(session, *args, **kwargs)
        except SQLAlchemyError:
            rollback(session)
            raise unavailable() from None
        except BusinessError:
            rollback(session)
            raise
    return wrapped


def can_retry(document, job, role, now):
    return bool(
        role in WRITERS and document.state == "failed" and document.error_code in RETRYABLE
        and document.uploaded_at is not None and document.finished_at is not None
        and document.finished_at <= now - timedelta(seconds=60)
        and job is not None and job.dispatch_state == "inactive"
        and job.attempt_count == 3 and job.manual_retry_count == 0
        and job.attempt_token is None and job.processing_lease_until is None
        and job.dispatch_token is None and job.dispatch_lease_until is None
    )


def metadata(document, job=None, role=None, now=None):
    result = DocumentRead.model_validate(document)
    result.can_retry = now is not None and can_retry(document, job, role, now)
    return result


def pair_query(workspace_id):
    return select(Document, DocumentJob).outerjoin(DocumentJob, and_(
        DocumentJob.document_id == Document.id, DocumentJob.workspace_id == Document.workspace_id,
    )).where(Document.workspace_id == workspace_id)


@database_operation
def read_document(session, workspace_id, document_id, role):
    pair = session.execute(pair_query(workspace_id).where(Document.id == document_id)).first()
    if pair is None:
        raise missing("document")
    return metadata(*pair, role, session.scalar(select(func.clock_timestamp())))


@database_operation
def list_documents(session, workspace_id, caller_id, role, params):
    conditions = [Document.workspace_id == workspace_id]
    if params.state is not None:
        conditions.append(Document.state == params.state)
    if params.upload_attempt_key is not None:
        conditions.extend((Document.upload_attempt_key == params.upload_attempt_key, Document.uploader_id == caller_id))
    total = session.scalar(select(func.count()).select_from(Document).where(*conditions))
    rows = session.execute(pair_query(workspace_id).where(*conditions).order_by(
        Document.created_at.desc(), Document.id.desc(),
    ).limit(params.limit).offset(params.offset)).all()
    now = session.scalar(select(func.clock_timestamp()))
    return [metadata(*pair, role, now) for pair in rows], total


@dataclass(frozen=True)
class Reservation:
    document_id: object
    storage_key: str
    token: object
    result: DocumentRead
    verify_object: bool


@database_operation
def reserve_upload(session, workspace_id, caller_id, key, received, role):
    document_id, now = session.execute(select(func.gen_random_uuid(), func.clock_timestamp())).one()
    token = uuid4()
    document = session.scalar(insert(Document).values(
        id=document_id, workspace_id=workspace_id, uploader_id=caller_id, upload_attempt_key=key,
        storage_key=new_key(workspace_id, document_id), original_filename=received.filename,
        byte_size=received.size, sha256=received.sha256, state="receiving",
        upload_token=token, upload_lease_until=now + timedelta(seconds=120), updated_at=now,
    ).on_conflict_do_nothing(constraint="uq_documents_upload_attempt").returning(Document))
    if document is not None:
        result = Reservation(document.id, document.storage_key, token, metadata(document), False)
        session.commit()
        return result
    document, job = session.execute(pair_query(workspace_id).where(
        Document.uploader_id == caller_id, Document.upload_attempt_key == key,
    )).one()
    if (document.sha256, document.byte_size, document.original_filename) != (received.sha256, received.size, received.filename):
        raise BusinessError(409, "conflict", "This upload attempt key was already used for another request.", [
            {"field": "idempotency_key", "message": "Use the original file or start a new upload attempt."},
        ])
    if document.state == "queued" and job is None:
        raise unavailable()
    result = Reservation(document.id, document.storage_key, None, metadata(document, job, role, now), document.uploaded_at is not None)
    session.rollback()
    return result


@database_operation
def finalize_upload(session, workspace_id, reservation):
    now = session.scalar(select(func.clock_timestamp()))
    document = session.scalar(update(Document).where(
        Document.workspace_id == workspace_id, Document.id == reservation.document_id,
        Document.state == "receiving", Document.upload_token == reservation.token,
        Document.upload_lease_until > func.clock_timestamp(),
    ).values(state="queued", uploaded_at=now, updated_at=now, upload_token=None, upload_lease_until=None).returning(Document))
    if document is None:
        raise unavailable()
    session.add(DocumentJob(
        workspace_id=workspace_id, document_id=document.id, dispatch_state="pending",
        next_dispatch_at=now, next_attempt_at=now,
    ))
    result = metadata(document)
    session.flush()
    session.commit()
    return result


@database_operation
def stored_reference(session, workspace_id, document_id, *, accepted=False):
    document = session.scalar(select(Document).where(Document.workspace_id == workspace_id, Document.id == document_id))
    if document is None:
        raise missing("document")
    if accepted and document.state != "accepted":
        raise BusinessError(409, "conflict", "Only accepted documents can be downloaded.")
    result = (document.storage_key, document.byte_size, document.sha256, document.detected_type)
    session.rollback()
    return result


@database_operation
def retry_document(session, workspace_id, document_id, role):
    document = session.scalar(select(Document).where(
        Document.workspace_id == workspace_id, Document.id == document_id,
    ).with_for_update().execution_options(populate_existing=True))
    if document is None:
        raise missing("document")
    job = session.scalar(select(DocumentJob).where(
        DocumentJob.workspace_id == workspace_id, DocumentJob.document_id == document_id,
    ).with_for_update().execution_options(populate_existing=True))
    now = session.scalar(select(func.clock_timestamp()))
    if not can_retry(document, job, role, now):
        raise BusinessError(409, "conflict", "This document is not eligible for another processing attempt.")
    document.state, document.error_code, document.finished_at, document.updated_at = "queued", None, None, now
    job.manual_retry_count = 1
    job.dispatch_state, job.next_attempt_at, job.next_dispatch_at, job.updated_at = "pending", now, now, now
    result = metadata(document)
    session.flush()
    session.commit()
    return result
