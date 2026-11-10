"""PostgreSQL owns scheduling. Every external operation happens after commit.

All writers lock document then job. Tokens AND database-clock lease checks fence
publishers, interrupted API uploads, and stale processing attempts.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text

from app.db import SessionLocal
from app.models import Document, DocumentJob

BATCH_SIZE = 20


@dataclass(frozen=True)
class Attempt:
    document_id: UUID
    workspace_id: UUID
    storage_key: str
    byte_size: int
    sha256: str
    token: UUID


class Jobs:
    def __init__(self, sessions=SessionLocal):
        self.sessions = sessions

    @contextmanager
    def transaction(self):
        with self.sessions() as session:
            with session.begin():
                session.execute(text("SET LOCAL lock_timeout = '3s'"))
                session.execute(text("SET LOCAL statement_timeout = '5s'"))
                yield session

    @staticmethod
    def pair(session, document_id, *, skip_locked=True):
        document = session.scalar(select(Document).where(Document.id == document_id).with_for_update(skip_locked=skip_locked))
        if document is None:
            return None, None
        job = session.scalar(select(DocumentJob).where(
            DocumentJob.document_id == document.id, DocumentJob.workspace_id == document.workspace_id,
        ).with_for_update(skip_locked=skip_locked))
        return document, job

    @staticmethod
    def clock(session):
        return session.scalar(select(func.clock_timestamp()))

    def candidates(self, kind):
        with self.transaction() as s:
            now = func.clock_timestamp()
            if kind == "uploads":
                query = select(Document.id).where(Document.state == "receiving", Document.upload_lease_until <= now).order_by(Document.upload_lease_until, Document.id)
            else:
                condition = (DocumentJob.processing_lease_until <= now) if kind == "processing" else or_(
                    DocumentJob.dispatch_state.in_(("pending", "published")) & (DocumentJob.next_dispatch_at <= now),
                    (DocumentJob.dispatch_state == "publishing") & (DocumentJob.dispatch_lease_until <= now),
                )
                query = select(DocumentJob.document_id).where(condition).order_by(DocumentJob.updated_at, DocumentJob.document_id)
            return list(s.scalars(query.limit(BATCH_SIZE)))

    def claim_dispatch(self, document_id):
        with self.transaction() as s:
            d, j = self.pair(s, document_id)
            now = self.clock(s)
            if d is None or j is None or d.state != "queued" or j.next_attempt_at is None or j.next_attempt_at > now:
                return None
            due = (j.dispatch_state in ("pending", "published") and j.next_dispatch_at <= now) or (
                j.dispatch_state == "publishing" and j.dispatch_lease_until <= now)
            if not due:
                return None
            token = uuid4()
            j.dispatch_state, j.dispatch_token = "publishing", token
            j.dispatch_lease_until, j.updated_at = now + timedelta(seconds=30), now
            return token

    def finish_dispatch(self, document_id, token, success):
        with self.transaction() as s:
            d, j = self.pair(s, document_id)
            now = self.clock(s)
            if j is None or d.state != "queued" or j.dispatch_token != token or j.dispatch_lease_until <= now:
                return False
            j.dispatch_token = j.dispatch_lease_until = None
            j.dispatch_state = "published" if success else "pending"
            j.next_dispatch_at = now + timedelta(seconds=180 if success else 30)
            if success:
                j.last_published_at = now
            j.updated_at = now
            return True

    def claim(self, document_id):
        with self.transaction() as s:
            # A publisher may still hold its short bookkeeping lock when delivery
            # arrives. Wait (lock_timeout=3s); a busy queued row is not a duplicate.
            d, j = self.pair(s, document_id, skip_locked=False)
            now = self.clock(s)
            if d is None or j is None or d.state != "queued" or j.attempt_token is not None or j.next_attempt_at is None or j.next_attempt_at > now or j.attempt_count >= 3 * (j.manual_retry_count + 1):
                return None
            j.attempt_count += 1
            j.attempt_token = uuid4()
            j.processing_lease_until = now + timedelta(seconds=120)
            self.inactive(j)
            d.state, d.updated_at, j.updated_at = "processing", now, now
            return Attempt(d.id, d.workspace_id, d.storage_key, d.byte_size, d.sha256, j.attempt_token)

    @staticmethod
    def inactive(j):
        j.dispatch_state = "inactive"
        j.dispatch_token = j.dispatch_lease_until = None
        j.next_dispatch_at = j.next_attempt_at = None

    @classmethod
    def outcome(cls, d, j, now, state, code=None, detected_type=None):
        cls.inactive(j)
        j.attempt_token = j.processing_lease_until = None
        d.updated_at = j.updated_at = now
        d.detected_type = detected_type
        if state == "temporary" and j.attempt_count < 3 * (j.manual_retry_count + 1):
            d.state, d.error_code, d.finished_at = "queued", None, None
            j.dispatch_state = "pending"
            delay = 10 if j.attempt_count % 3 == 1 else 30
            j.next_dispatch_at = j.next_attempt_at = now + timedelta(seconds=delay)
        else:
            d.state = "failed" if state == "temporary" else state
            d.error_code, d.finished_at = code, now

    def complete(self, attempt, state, code=None, detected_type=None):
        with self.transaction() as s:
            d, j = self.pair(s, attempt.document_id, skip_locked=False)
            now = self.clock(s)
            if d is None or j is None or d.state != "processing" or j.attempt_token != attempt.token or j.processing_lease_until <= now:
                return False
            self.outcome(d, j, now, state, code, detected_type)
            return True

    def recover_processing(self, document_id):
        with self.transaction() as s:
            d, j = self.pair(s, document_id)
            now = self.clock(s)
            if d is None or j is None or d.state != "processing" or j.processing_lease_until is None or j.processing_lease_until > now:
                return False
            self.outcome(d, j, now, "temporary", "processing_interrupted")
            return True

    def claim_upload(self, document_id):
        with self.transaction() as s:
            d, _ = self.pair(s, document_id)
            now = self.clock(s)
            if d is None or d.state != "receiving" or d.upload_lease_until > now:
                return None
            d.upload_token, d.upload_lease_until, d.updated_at = uuid4(), now + timedelta(seconds=120), now
            return Attempt(d.id, d.workspace_id, d.storage_key, d.byte_size, d.sha256, d.upload_token)

    def finish_upload(self, attempt, result):
        with self.transaction() as s:
            d, j = self.pair(s, attempt.document_id)
            now = self.clock(s)
            if d is None or d.state != "receiving" or d.upload_token != attempt.token or d.upload_lease_until <= now:
                return False
            if result == "unavailable" and now < d.created_at + timedelta(minutes=15):
                return False  # Keep lease; next reconciliation is bounded, not a hot loop.
            d.upload_token = d.upload_lease_until = None
            d.updated_at = now
            if result == "ready":
                d.state, d.uploaded_at = "queued", now
                s.add(DocumentJob(document_id=d.id, workspace_id=d.workspace_id, dispatch_state="pending", next_attempt_at=now, next_dispatch_at=now))
            else:
                d.state, d.finished_at = "failed", now
                d.error_code = "storage_integrity" if result == "integrity" else "upload_incomplete"
            return True

    def may_delete(self, storage_key):
        with self.transaction() as s:
            d = s.scalar(select(Document).where(Document.storage_key == storage_key))
            # Keys are server-generated, immutable, never reused or adopted by uploads.
            return d is None or (d.state == "failed" and d.error_code == "upload_incomplete")
