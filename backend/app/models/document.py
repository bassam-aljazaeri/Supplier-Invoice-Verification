"""Private document metadata, independent of manually entered invoices."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, WorkspaceRecord, scoped_constraints, text_check


class DocumentState(StrEnum):
    RECEIVING = "receiving"
    QUEUED = "queued"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class DocumentType(StrEnum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"


class DocumentErrorCode(StrEnum):
    INVALID_FILE = "invalid_file"
    UNSUPPORTED_TYPE = "unsupported_type"
    PDF_ENCRYPTED = "pdf_encrypted"
    PDF_PAGE_COUNT = "pdf_page_count"
    IMAGE_FRAME_COUNT = "image_frame_count"
    IMAGE_DIMENSIONS = "image_dimensions"
    PARSER_LIMIT = "parser_limit"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    PROCESSING_INTERRUPTED = "processing_interrupted"
    PROCESSING_ERROR = "processing_error"
    UPLOAD_INCOMPLETE = "upload_incomplete"
    STORAGE_INTEGRITY = "storage_integrity"


class Document(WorkspaceRecord, Base):
    __tablename__ = "documents"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "uploader_id", "upload_attempt_key", name="uq_documents_upload_attempt"),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        Index("ix_documents_uploader", "uploader_id"),
        Index("ix_documents_receiving_lease", "upload_lease_until", postgresql_where=text("state = 'receiving'")),
        text_check(__tablename__, "storage_key"),
        CheckConstraint(
            "original_filename !~ '^[[:space:]]*$' AND original_filename !~ '[[:cntrl:]]' "
            "AND strpos(original_filename, '/') = 0 AND strpos(original_filename, chr(92)) = 0 "
            "AND original_filename NOT IN ('.', '..')",
            name="ck_documents_original_filename",
        ),
        CheckConstraint("byte_size BETWEEN 1 AND 5000000", name="ck_documents_byte_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256"),
        CheckConstraint("detected_type IN ('pdf', 'jpeg', 'png')", name="ck_documents_detected_type"),
        CheckConstraint(
            "state IN ('receiving', 'queued', 'processing', 'accepted', 'rejected', 'failed')",
            name="ck_documents_state",
        ),
        CheckConstraint(
            "(state IN ('receiving', 'queued', 'processing', 'accepted') AND error_code IS NULL) OR "
            "(state = 'rejected' AND error_code IS NOT NULL AND error_code IN "
            "('invalid_file', 'unsupported_type', 'pdf_encrypted', 'pdf_page_count', "
            "'image_frame_count', 'image_dimensions', 'parser_limit')) OR "
            "(state = 'failed' AND error_code IS NOT NULL AND error_code IN "
            "('storage_unavailable', 'processing_interrupted', 'processing_error', 'upload_incomplete', 'storage_integrity'))",
            name="ck_documents_state_error",
        ),
        CheckConstraint("state <> 'accepted' OR detected_type IS NOT NULL", name="ck_documents_accepted_type"),
        CheckConstraint(
            "(state = 'receiving' AND upload_token IS NOT NULL AND upload_lease_until IS NOT NULL) OR "
            "(state <> 'receiving' AND upload_token IS NULL AND upload_lease_until IS NULL)",
            name="ck_documents_upload_ownership",
        ),
        CheckConstraint(
            "(state = 'receiving' AND uploaded_at IS NULL) OR "
            "(state IN ('queued', 'processing', 'accepted', 'rejected') AND uploaded_at IS NOT NULL) OR "
            "(state = 'failed' AND ((error_code = 'upload_incomplete' AND uploaded_at IS NULL) OR "
            "error_code = 'storage_integrity' OR "
            "(error_code IN ('storage_unavailable', 'processing_interrupted', 'processing_error') AND uploaded_at IS NOT NULL)))",
            name="ck_documents_uploaded_state",
        ),
        CheckConstraint(
            "(state IN ('accepted', 'rejected', 'failed') AND finished_at IS NOT NULL) OR "
            "(state IN ('receiving', 'queued', 'processing') AND finished_at IS NULL)",
            name="ck_documents_finished_state",
        ),
    )

    uploader_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_users.id", name="fk_documents_uploader", ondelete="RESTRICT"), nullable=False,
    )
    upload_attempt_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(4))
    state: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'receiving'"))
    error_code: Mapped[str | None] = mapped_column(String(32))
    upload_token: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    upload_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    uploader: Mapped["ApplicationUser"] = relationship("ApplicationUser", foreign_keys=[uploader_id])
    job: Mapped["DocumentJob | None"] = relationship(
        "DocumentJob", back_populates="document", uselist=False,
        primaryjoin="and_(Document.workspace_id == DocumentJob.workspace_id, "
                    "Document.id == foreign(DocumentJob.document_id))",
    )
