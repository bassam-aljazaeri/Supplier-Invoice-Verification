from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, Date, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, MONEY_MAX, PRICE_MAX, QUANTITY_MAX, WorkspaceRecord, date_check, number_check, scoped_constraints, text_check


class Invoice(WorkspaceRecord, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "supplier_id", "invoice_number", name="uq_invoices_supplier_number"),
        UniqueConstraint("workspace_id", "id", "purchase_order_id", name="uq_invoices_order_id"),
        ForeignKeyConstraint(
            ["workspace_id", "supplier_id"], ["suppliers.workspace_id", "suppliers.id"],
            name="fk_invoices_supplier", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "supplier_id", "purchase_order_id"],
            ["purchase_orders.workspace_id", "purchase_orders.supplier_id", "purchase_orders.id"],
            name="fk_invoices_supplier_order", ondelete="RESTRICT", match="SIMPLE",
        ),
        Index("ix_invoices_order", "workspace_id", "purchase_order_id"),
        text_check(__tablename__, "invoice_number"),
        text_check(__tablename__, "notes", optional=True),
        date_check(__tablename__, "invoice_date"),
        date_check(__tablename__, "due_date", optional=True),
        CheckConstraint("due_date IS NULL OR due_date >= invoice_date", name="ck_invoices_due_date"),
        CheckConstraint("currency = 'EUR'", name="ck_invoices_currency"),
        CheckConstraint("status = 'draft'", name="ck_invoices_status"),
        number_check(__tablename__, "subtotal", MONEY_MAX),
        number_check(__tablename__, "tax_amount", MONEY_MAX),
        number_check(__tablename__, "total", MONEY_MAX),
        CheckConstraint("total = subtotal + tax_amount", name="ck_invoices_total"),
    )

    supplier_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'draft'"))
    notes: Mapped[str | None] = mapped_column(String(2000))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="invoices",
        primaryjoin="and_(Invoice.workspace_id == Supplier.workspace_id, "
                    "foreign(Invoice.supplier_id) == Supplier.id)",
    )
    purchase_order: Mapped["PurchaseOrder | None"] = relationship(
        "PurchaseOrder", back_populates="invoices",
        primaryjoin="and_(Invoice.workspace_id == PurchaseOrder.workspace_id, "
                    "Invoice.supplier_id == PurchaseOrder.supplier_id, "
                    "foreign(Invoice.purchase_order_id) == PurchaseOrder.id)",
    )
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", order_by="InvoiceLine.line_no",
        primaryjoin="and_(Invoice.workspace_id == InvoiceLine.workspace_id, "
                    "Invoice.id == foreign(InvoiceLine.invoice_id))",
    )


class InvoiceLine(WorkspaceRecord, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "invoice_id", "line_no", name="uq_invoice_lines_line_no"),
        ForeignKeyConstraint(
            ["workspace_id", "invoice_id"], ["invoices.workspace_id", "invoices.id"],
            name="fk_invoice_lines_invoice", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "invoice_id", "purchase_order_id"],
            ["invoices.workspace_id", "invoices.id", "invoices.purchase_order_id"],
            name="fk_invoice_lines_invoice_order", ondelete="RESTRICT", match="SIMPLE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "purchase_order_id", "purchase_order_line_id"],
            ["purchase_order_lines.workspace_id", "purchase_order_lines.purchase_order_id", "purchase_order_lines.id"],
            name="fk_invoice_lines_order_line", ondelete="RESTRICT", match="SIMPLE",
        ),
        Index("ix_invoice_lines_order_line", "workspace_id", "purchase_order_id", "purchase_order_line_id"),
        CheckConstraint(
            "(purchase_order_id IS NULL) = (purchase_order_line_id IS NULL)",
            name="ck_invoice_lines_mapping_pair",
        ),
        CheckConstraint("line_no > 0", name="ck_invoice_lines_line_no"),
        text_check(__tablename__, "description"),
        number_check(__tablename__, "quantity", QUANTITY_MAX, positive=True),
        number_check(__tablename__, "unit_price", PRICE_MAX),
        number_check(__tablename__, "line_total", MONEY_MAX),
    )

    invoice_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    purchase_order_line_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    purchase_order_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    invoice: Mapped[Invoice] = relationship(
        back_populates="lines",
        primaryjoin="and_(InvoiceLine.workspace_id == Invoice.workspace_id, "
                    "foreign(InvoiceLine.invoice_id) == Invoice.id)",
    )
    # Assign mapping IDs explicitly together; this read relation must not copy an
    # order ID over the header's ownership or leave an incomplete nullable pair.
    purchase_order_line: Mapped["PurchaseOrderLine | None"] = relationship(
        "PurchaseOrderLine", viewonly=True,
        primaryjoin="and_(InvoiceLine.workspace_id == PurchaseOrderLine.workspace_id, "
                    "InvoiceLine.purchase_order_id == PurchaseOrderLine.purchase_order_id, "
                    "foreign(InvoiceLine.purchase_order_line_id) == PurchaseOrderLine.id)",
    )
