from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Date, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base, MONEY_MAX, PRICE_MAX, QUANTITY_MAX, WorkspaceRecord, date_check,
    number_check, scoped_constraints, text_check,
)


class PurchaseOrder(WorkspaceRecord, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "po_number", name="uq_purchase_orders_number"),
        UniqueConstraint("workspace_id", "supplier_id", "id", name="uq_purchase_orders_supplier_id"),
        ForeignKeyConstraint(
            ["workspace_id", "supplier_id"], ["suppliers.workspace_id", "suppliers.id"],
            name="fk_purchase_orders_supplier", ondelete="RESTRICT",
        ),
        Index("ix_purchase_orders_supplier", "workspace_id", "supplier_id"),
        text_check(__tablename__, "po_number"),
        text_check(__tablename__, "notes", optional=True),
        date_check(__tablename__, "order_date"),
        CheckConstraint("currency = 'EUR'", name="ck_purchase_orders_currency"),
        number_check(__tablename__, "subtotal", MONEY_MAX),
    )

    supplier_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    po_number: Mapped[str] = mapped_column(String(64), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="purchase_orders",
        primaryjoin="and_(PurchaseOrder.workspace_id == Supplier.workspace_id, "
                    "foreign(PurchaseOrder.supplier_id) == Supplier.id)",
    )
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="purchase_order", order_by="PurchaseOrderLine.line_no",
        primaryjoin="and_(PurchaseOrder.workspace_id == PurchaseOrderLine.workspace_id, "
                    "PurchaseOrder.id == foreign(PurchaseOrderLine.purchase_order_id))",
    )
    delivery_receipts: Mapped[list["DeliveryReceipt"]] = relationship(
        "DeliveryReceipt", back_populates="purchase_order",
        primaryjoin="and_(PurchaseOrder.workspace_id == DeliveryReceipt.workspace_id, "
                    "PurchaseOrder.id == foreign(DeliveryReceipt.purchase_order_id))",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="purchase_order",
        primaryjoin="and_(PurchaseOrder.workspace_id == Invoice.workspace_id, "
                    "PurchaseOrder.supplier_id == Invoice.supplier_id, "
                    "PurchaseOrder.id == foreign(Invoice.purchase_order_id))",
    )


class PurchaseOrderLine(WorkspaceRecord, Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "purchase_order_id", "id", name="uq_order_lines_order_id"),
        UniqueConstraint("workspace_id", "purchase_order_id", "line_no", name="uq_order_lines_line_no"),
        ForeignKeyConstraint(
            ["workspace_id", "purchase_order_id"],
            ["purchase_orders.workspace_id", "purchase_orders.id"],
            name="fk_order_lines_order", ondelete="RESTRICT",
        ),
        CheckConstraint("line_no > 0", name="ck_order_lines_line_no"),
        text_check(__tablename__, "description"),
        number_check(__tablename__, "quantity", QUANTITY_MAX, positive=True),
        number_check(__tablename__, "unit_price", PRICE_MAX),
        number_check(__tablename__, "line_total", MONEY_MAX),
    )

    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        back_populates="lines",
        primaryjoin="and_(PurchaseOrderLine.workspace_id == PurchaseOrder.workspace_id, "
                    "foreign(PurchaseOrderLine.purchase_order_id) == PurchaseOrder.id)",
    )
