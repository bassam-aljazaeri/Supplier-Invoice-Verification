"""Add application identities and workspace memberships without changing records.

Revision ID: 0002_auth_workspaces
Revises: 0001_manual_records
Schema only: no users, memberships, or business data are inserted.
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_auth_workspaces"
down_revision = "0001_manual_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("issuer <> '' AND issuer = regexp_replace(issuer, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name="ck_application_users_issuer_text"),
        sa.CheckConstraint("subject <> '' AND subject = regexp_replace(subject, '^[[:space:]]+|[[:space:]]+$', '', 'g')", name="ck_application_users_subject_text"),
        sa.PrimaryKeyConstraint("id", name="pk_application_users"),
        sa.UniqueConstraint("issuer", "subject", name="uq_application_users_issuer_subject"),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("application_user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.CheckConstraint("role IN ('administrator', 'accountant', 'approver')", name="ck_workspace_memberships_role"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_memberships_workspace", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_user_id"], ["application_users.id"], name="fk_workspace_memberships_user", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_memberships"),
        sa.UniqueConstraint("workspace_id", "application_user_id", name="uq_workspace_memberships_workspace_user"),
    )
    op.create_index("ix_workspace_memberships_user_workspace", "workspace_memberships", ["application_user_id", "workspace_id"])
    op.create_index("ix_workspace_memberships_workspace_role", "workspace_memberships", ["workspace_id", "role"])
    op.create_index("ix_workspace_memberships_workspace_created_id", "workspace_memberships", ["workspace_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_memberships_workspace_created_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_workspace_role", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user_workspace", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("application_users")
