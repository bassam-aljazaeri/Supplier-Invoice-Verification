from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, QUANTITY_MAX, WorkspaceRecord, date_check, number_check, scoped_constraints, text_check


class DeliveryReceipt(WorkspaceRecord, Base):
    __tablename__ = "delivery_receipts"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "receipt_number", name="uq_delivery_receipts_number"),
        UniqueConstraint("workspace_id", "id", "purchase_order_id", name="uq_delivery_receipts_order_id"),
        ForeignKeyConstraint(
            ["workspace_id", "purchase_order_id"],
            ["purchase_orders.workspace_id", "purchase_orders.id"],
            name="fk_delivery_receipts_order", ondelete="RESTRICT",
        ),
        Index("ix_delivery_receipts_order", "workspace_id", "purchase_order_id"),
        text_check(__tablename__, "receipt_number"),
        text_check(__tablename__, "notes", optional=True),
        date_check(__tablename__, "received_date"),
    )

    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(64), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000))

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="delivery_receipts",
        primaryjoin="and_(DeliveryReceipt.workspace_id == PurchaseOrder.workspace_id, "
                    "foreign(DeliveryReceipt.purchase_order_id) == PurchaseOrder.id)",
    )
    lines: Mapped[list["DeliveryReceiptLine"]] = relationship(
        "DeliveryReceiptLine", back_populates="delivery_receipt", order_by="DeliveryReceiptLine.line_no",
        primaryjoin="and_(DeliveryReceipt.workspace_id == DeliveryReceiptLine.workspace_id, "
                    "DeliveryReceipt.id == foreign(DeliveryReceiptLine.delivery_receipt_id), "
                    "DeliveryReceipt.purchase_order_id == foreign(DeliveryReceiptLine.purchase_order_id))",
    )


class DeliveryReceiptLine(WorkspaceRecord, Base):
    __tablename__ = "delivery_receipt_lines"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "delivery_receipt_id", "line_no", name="uq_receipt_lines_line_no"),
        UniqueConstraint("workspace_id", "delivery_receipt_id", "purchase_order_line_id", name="uq_receipt_lines_order_line"),
        ForeignKeyConstraint(
            ["workspace_id", "delivery_receipt_id", "purchase_order_id"],
            ["delivery_receipts.workspace_id", "delivery_receipts.id", "delivery_receipts.purchase_order_id"],
            name="fk_receipt_lines_receipt_order", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "purchase_order_id", "purchase_order_line_id"],
            ["purchase_order_lines.workspace_id", "purchase_order_lines.purchase_order_id", "purchase_order_lines.id"],
            name="fk_receipt_lines_order_line", ondelete="RESTRICT",
        ),
        Index("ix_receipt_lines_order_line", "workspace_id", "purchase_order_id", "purchase_order_line_id"),
        CheckConstraint("line_no > 0", name="ck_receipt_lines_line_no"),
        number_check(__tablename__, "quantity_received", QUANTITY_MAX, positive=True),
    )

    delivery_receipt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    purchase_order_line_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    delivery_receipt: Mapped[DeliveryReceipt] = relationship(
        back_populates="lines",
        primaryjoin="and_(DeliveryReceiptLine.workspace_id == DeliveryReceipt.workspace_id, "
                    "foreign(DeliveryReceiptLine.delivery_receipt_id) == DeliveryReceipt.id, "
                    "foreign(DeliveryReceiptLine.purchase_order_id) == DeliveryReceipt.purchase_order_id)",
    )
    purchase_order_line: Mapped["PurchaseOrderLine"] = relationship(
        "PurchaseOrderLine", viewonly=True,
        primaryjoin="and_(DeliveryReceiptLine.workspace_id == PurchaseOrderLine.workspace_id, "
                    "DeliveryReceiptLine.purchase_order_id == PurchaseOrderLine.purchase_order_id, "
                    "foreign(DeliveryReceiptLine.purchase_order_line_id) == PurchaseOrderLine.id)",
    )
