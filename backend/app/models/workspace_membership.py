"""A single application role for one user in one workspace."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, WorkspaceRecord


class MembershipRole(StrEnum):
    ADMINISTRATOR = "administrator"
    ACCOUNTANT = "accountant"
    APPROVER = "approver"


class WorkspaceMembership(WorkspaceRecord, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "application_user_id", name="uq_workspace_memberships_workspace_user"),
        CheckConstraint(
            "role IN ('administrator', 'accountant', 'approver')",
            name="ck_workspace_memberships_role",
        ),
        Index("ix_workspace_memberships_user_workspace", "application_user_id", "workspace_id"),
        Index("ix_workspace_memberships_workspace_role", "workspace_id", "role"),
        Index("ix_workspace_memberships_workspace_created_id", "workspace_id", "created_at", "id"),
    )

    application_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_users.id", name="fk_workspace_memberships_user", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    application_user: Mapped["ApplicationUser"] = relationship(
        "ApplicationUser", foreign_keys=[application_user_id],
    )
