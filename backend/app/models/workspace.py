from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Record, text_check


class Workspace(Record, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_workspaces_slug"),
        text_check("workspaces", "slug"),
        text_check("workspaces", "name"),
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    suppliers: Mapped[list["Supplier"]] = relationship(
        "Supplier", foreign_keys="Supplier.workspace_id", viewonly=True
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder", foreign_keys="PurchaseOrder.workspace_id", viewonly=True
    )
    delivery_receipts: Mapped[list["DeliveryReceipt"]] = relationship(
        "DeliveryReceipt", foreign_keys="DeliveryReceipt.workspace_id", viewonly=True
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", foreign_keys="Invoice.workspace_id", viewonly=True
    )
