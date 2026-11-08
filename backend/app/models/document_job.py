"""One durable dispatch/processing record per document; no Celery result copy."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DispatchState(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    INACTIVE = "inactive"


class DocumentJob(Base):
    __tablename__ = "document_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "document_id"], ["documents.workspace_id", "documents.id"],
            name="fk_document_jobs_document", ondelete="RESTRICT",
        ),
        Index(
            "ix_document_jobs_due_dispatch", "next_dispatch_at", "document_id",
            postgresql_where=text("dispatch_state IN ('pending', 'published')"),
        ),
        Index(
            "ix_document_jobs_publishing_lease", "dispatch_lease_until",
            postgresql_where=text("dispatch_state = 'publishing'"),
        ),
        Index(
            "ix_document_jobs_processing_lease", "processing_lease_until",
            postgresql_where=text("processing_lease_until IS NOT NULL"),
        ),
        CheckConstraint(
            "dispatch_state IN ('pending', 'publishing', 'published', 'inactive')",
            name="ck_document_jobs_dispatch_state",
        ),
        CheckConstraint("attempt_count BETWEEN 0 AND 6", name="ck_document_jobs_attempt_count"),
        CheckConstraint("manual_retry_count BETWEEN 0 AND 1", name="ck_document_jobs_manual_retry_count"),
        CheckConstraint(
            "attempt_count <= 3 * (manual_retry_count + 1) AND (manual_retry_count = 0 OR attempt_count >= 3)",
            name="ck_document_jobs_retry_budget",
        ),
        CheckConstraint(
            "(dispatch_state = 'publishing' AND dispatch_token IS NOT NULL AND dispatch_lease_until IS NOT NULL) OR "
            "(dispatch_state <> 'publishing' AND dispatch_token IS NULL AND dispatch_lease_until IS NULL)",
            name="ck_document_jobs_dispatch_ownership",
        ),
        CheckConstraint(
            "(attempt_token IS NULL) = (processing_lease_until IS NULL)",
            name="ck_document_jobs_processing_ownership",
        ),
        CheckConstraint(
            "attempt_token IS NULL OR (dispatch_state = 'inactive' AND attempt_count > 0)",
            name="ck_document_jobs_processing_claim",
        ),
        CheckConstraint(
            "(dispatch_state = 'inactive' AND next_dispatch_at IS NULL AND next_attempt_at IS NULL) OR "
            "(dispatch_state <> 'inactive' AND next_dispatch_at IS NOT NULL AND next_attempt_at IS NOT NULL "
            "AND attempt_count < 3 * (manual_retry_count + 1))",
            name="ck_document_jobs_schedule",
        ),
        CheckConstraint(
            "dispatch_state <> 'published' OR last_published_at IS NOT NULL",
            name="ck_document_jobs_published_at",
        ),
    )

    # The document ID is the job's primary key, not a newly generated job UUID.
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", name="fk_document_jobs_workspace", ondelete="RESTRICT"), nullable=False,
    )
    dispatch_state: Mapped[str] = mapped_column(String(16), nullable=False)
    next_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    dispatch_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    manual_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempt_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    processing_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    workspace: Mapped["Workspace"] = relationship("Workspace", foreign_keys=[workspace_id])
    document: Mapped["Document"] = relationship(
        "Document", back_populates="job",
        primaryjoin="and_(DocumentJob.workspace_id == Document.workspace_id, "
                    "foreign(DocumentJob.document_id) == Document.id)",
    )
