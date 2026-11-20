"""Add private document metadata and durable jobs without changing business rows.

Revision ID: 0003_documents
Revises: 0002_auth_workspaces
Schema only: no documents, jobs, invoices, or other records are inserted.
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_documents"
down_revision = "0002_auth_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("uploader_id", sa.UUID(), nullable=False),
        sa.Column("upload_attempt_key", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("detected_type", sa.String(4), nullable=True),
        sa.Column("state", sa.String(16), server_default=sa.text("'receiving'"), nullable=False),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("upload_token", sa.UUID(), nullable=True),
        sa.Column("upload_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_documents_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_id"], ["application_users.id"], name="fk_documents_uploader", ondelete="RESTRICT"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_documents_workspace_id"),
        sa.UniqueConstraint("workspace_id", "uploader_id", "upload_attempt_key", name="uq_documents_upload_attempt"),
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        sa.CheckConstraint(
            "storage_key <> '' AND storage_key = regexp_replace(storage_key, '^[[:space:]]+|[[:space:]]+$', '', 'g')",
            name="ck_documents_storage_key_text",
        ),
        sa.CheckConstraint(
            "original_filename !~ '^[[:space:]]*$' AND original_filename !~ '[[:cntrl:]]' "
            "AND strpos(original_filename, '/') = 0 AND strpos(original_filename, chr(92)) = 0 "
            "AND original_filename NOT IN ('.', '..')",
            name="ck_documents_original_filename",
        ),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 5000000", name="ck_documents_byte_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256"),
        sa.CheckConstraint("detected_type IN ('pdf', 'jpeg', 'png')", name="ck_documents_detected_type"),
        sa.CheckConstraint(
            "state IN ('receiving', 'queued', 'processing', 'accepted', 'rejected', 'failed')",
            name="ck_documents_state",
        ),
        sa.CheckConstraint(
            "(state IN ('receiving', 'queued', 'processing', 'accepted') AND error_code IS NULL) OR "
            "(state = 'rejected' AND error_code IS NOT NULL AND error_code IN "
            "('invalid_file', 'unsupported_type', 'pdf_encrypted', 'pdf_page_count', "
            "'image_frame_count', 'image_dimensions', 'parser_limit')) OR "
            "(state = 'failed' AND error_code IS NOT NULL AND error_code IN "
            "('storage_unavailable', 'processing_interrupted', 'processing_error', 'upload_incomplete', 'storage_integrity'))",
            name="ck_documents_state_error",
        ),
        sa.CheckConstraint("state <> 'accepted' OR detected_type IS NOT NULL", name="ck_documents_accepted_type"),
        sa.CheckConstraint(
            "(state = 'receiving' AND upload_token IS NOT NULL AND upload_lease_until IS NOT NULL) OR "
            "(state <> 'receiving' AND upload_token IS NULL AND upload_lease_until IS NULL)",
            name="ck_documents_upload_ownership",
        ),
        sa.CheckConstraint(
            "(state = 'receiving' AND uploaded_at IS NULL) OR "
            "(state IN ('queued', 'processing', 'accepted', 'rejected') AND uploaded_at IS NOT NULL) OR "
            "(state = 'failed' AND ((error_code = 'upload_incomplete' AND uploaded_at IS NULL) OR "
            "error_code = 'storage_integrity' OR "
            "(error_code IN ('storage_unavailable', 'processing_interrupted', 'processing_error') AND uploaded_at IS NOT NULL)))",
            name="ck_documents_uploaded_state",
        ),
        sa.CheckConstraint(
            "(state IN ('accepted', 'rejected', 'failed') AND finished_at IS NOT NULL) OR "
            "(state IN ('receiving', 'queued', 'processing') AND finished_at IS NULL)",
            name="ck_documents_finished_state",
        ),
    )
    op.create_index("ix_documents_workspace_created_id", "documents", ["workspace_id", "created_at", "id"])
    op.create_index("ix_documents_uploader", "documents", ["uploader_id"])
    op.create_index("ix_documents_receiving_lease", "documents", ["upload_lease_until"], postgresql_where=sa.text("state = 'receiving'"))
    op.create_table(
        "document_jobs",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("dispatch_state", sa.String(16), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatch_token", sa.UUID(), nullable=True),
        sa.Column("dispatch_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("manual_retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("attempt_token", sa.UUID(), nullable=True),
        sa.Column("processing_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_document_jobs")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_document_jobs_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"], ["documents.workspace_id", "documents.id"],
            name="fk_document_jobs_document", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "dispatch_state IN ('pending', 'publishing', 'published', 'inactive')",
            name="ck_document_jobs_dispatch_state",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 6", name="ck_document_jobs_attempt_count"),
        sa.CheckConstraint("manual_retry_count BETWEEN 0 AND 1", name="ck_document_jobs_manual_retry_count"),
        sa.CheckConstraint(
            "attempt_count <= 3 * (manual_retry_count + 1) AND (manual_retry_count = 0 OR attempt_count >= 3)",
            name="ck_document_jobs_retry_budget",
        ),
        sa.CheckConstraint(
            "(dispatch_state = 'publishing' AND dispatch_token IS NOT NULL AND dispatch_lease_until IS NOT NULL) OR "
            "(dispatch_state <> 'publishing' AND dispatch_token IS NULL AND dispatch_lease_until IS NULL)",
            name="ck_document_jobs_dispatch_ownership",
        ),
        sa.CheckConstraint(
            "(attempt_token IS NULL) = (processing_lease_until IS NULL)",
            name="ck_document_jobs_processing_ownership",
        ),
        sa.CheckConstraint(
            "attempt_token IS NULL OR (dispatch_state = 'inactive' AND attempt_count > 0)",
            name="ck_document_jobs_processing_claim",
        ),
        sa.CheckConstraint(
            "(dispatch_state = 'inactive' AND next_dispatch_at IS NULL AND next_attempt_at IS NULL) OR "
            "(dispatch_state <> 'inactive' AND next_dispatch_at IS NOT NULL AND next_attempt_at IS NOT NULL "
            "AND attempt_count < 3 * (manual_retry_count + 1))",
            name="ck_document_jobs_schedule",
        ),
        sa.CheckConstraint(
            "dispatch_state <> 'published' OR last_published_at IS NOT NULL",
            name="ck_document_jobs_published_at",
        ),
    )
    op.create_index(
        "ix_document_jobs_due_dispatch", "document_jobs", ["next_dispatch_at", "document_id"],
        postgresql_where=sa.text("dispatch_state IN ('pending', 'published')"),
    )
    op.create_index(
        "ix_document_jobs_publishing_lease", "document_jobs", ["dispatch_lease_until"],
        postgresql_where=sa.text("dispatch_state = 'publishing'"),
    )
    op.create_index(
        "ix_document_jobs_processing_lease", "document_jobs", ["processing_lease_until"],
        postgresql_where=sa.text("processing_lease_until IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_document_jobs_processing_lease", table_name="document_jobs")
    op.drop_index("ix_document_jobs_publishing_lease", table_name="document_jobs")
    op.drop_index("ix_document_jobs_due_dispatch", table_name="document_jobs")
    op.drop_table("document_jobs")
    op.drop_index("ix_documents_receiving_lease", table_name="documents")
    op.drop_index("ix_documents_uploader", table_name="documents")
    op.drop_index("ix_documents_workspace_created_id", table_name="documents")
    op.drop_table("documents")
