"""Shared metadata and schema-only helpers, not business calculation services."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, MetaData, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})


class Record:
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class WorkspaceRecord(Record):
    @declared_attr
    def workspace_id(cls) -> Mapped[UUID]:
        return mapped_column(
            PG_UUID(as_uuid=True),
            ForeignKey(
                "workspaces.id", name=f"fk_{cls.__tablename__}_workspace",
                ondelete="RESTRICT",
            ),
            nullable=False,
        )

    @declared_attr
    def workspace(cls):
        return relationship("Workspace", foreign_keys=lambda: [cls.workspace_id])


def scoped_constraints(table: str) -> tuple:
    return (
        UniqueConstraint("workspace_id", "id", name=f"uq_{table}_workspace_id"),
        Index(f"ix_{table}_workspace_created_id", "workspace_id", "created_at", "id"),
    )


def text_check(table: str, column: str, *, optional: bool = False) -> CheckConstraint:
    # POSIX whitespace includes tabs/newlines, unlike btrim's space-only default.
    expression = (
        f"{column} <> '' AND "
        f"{column} = regexp_replace({column}, '^[[:space:]]+|[[:space:]]+$', '', 'g')"
    )
    if optional:
        expression = f"{column} IS NULL OR ({expression})"
    return CheckConstraint(expression, name=f"ck_{table}_{column}_text")


def number_check(table: str, column: str, maximum: str, *, positive: bool = False):
    return CheckConstraint(
        f"{column} {'>' if positive else '>='} 0 AND {column} <= {maximum}",
        name=f"ck_{table}_{column}_range",
    )


def date_check(table: str, column: str, *, optional: bool = False):
    expression = f"{column} BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'"
    if optional:
        expression = f"{column} IS NULL OR ({expression})"
    return CheckConstraint(expression, name=f"ck_{table}_{column}_range")


QUANTITY_MAX = "999999999.999"
PRICE_MAX = "9999999999.9999"
MONEY_MAX = "9999999999999999.99"
