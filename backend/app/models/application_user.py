"""Application identity; email and workspace permissions are not identity keys."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Record, text_check


class ApplicationUser(Record, Base):
    __tablename__ = "application_users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_application_users_issuer_subject"),
        text_check("application_users", "issuer"),
        text_check("application_users", "subject"),
    )

    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        "WorkspaceMembership", foreign_keys="WorkspaceMembership.application_user_id", viewonly=True,
    )
