from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, WorkspaceRecord, scoped_constraints, text_check


class Supplier(WorkspaceRecord, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        *scoped_constraints(__tablename__),
        UniqueConstraint("workspace_id", "supplier_code", name="uq_suppliers_code"),
        text_check(__tablename__, "supplier_code"),
        text_check(__tablename__, "name"),
        text_check(__tablename__, "notes", optional=True),
    )

    supplier_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000))

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder", back_populates="supplier",
        primaryjoin="and_(Supplier.workspace_id == PurchaseOrder.workspace_id, "
                    "Supplier.id == foreign(PurchaseOrder.supplier_id))",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="supplier",
        primaryjoin="and_(Supplier.workspace_id == Invoice.workspace_id, "
                    "Supplier.id == foreign(Invoice.supplier_id))",
    )
