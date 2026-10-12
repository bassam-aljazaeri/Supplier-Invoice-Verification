"""Import every model so Alembic and ORM configuration share complete metadata."""

from app.models.base import Base
from app.models.workspace import Workspace
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.delivery_receipt import DeliveryReceipt, DeliveryReceiptLine
from app.models.invoice import Invoice, InvoiceLine

__all__ = [
    "Base", "Workspace", "Supplier", "PurchaseOrder", "PurchaseOrderLine",
    "DeliveryReceipt", "DeliveryReceiptLine", "Invoice", "InvoiceLine",
]
