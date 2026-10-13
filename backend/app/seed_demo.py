"""Explicit, atomic fictional workflow initialization: python -m app.seed_demo."""

import sys
from uuid import UUID

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine, PurchaseOrder, PurchaseOrderLine, Supplier
from app.schemas.delivery_receipt import DeliveryReceiptCreate
from app.schemas.invoice import InvoiceCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.supplier import SupplierCreate
from app.seed_workspace import WorkspaceConflict, ensure_demo_workspace
from app.services import manual_records
from app.workspace import DEMO_WORKSPACE_ID

DEMO_SUPPLIER_ID = UUID("10000000-0000-4000-8000-000000000001")
DEMO_ORDER_ID = UUID("20000000-0000-4000-8000-000000000001")
DEMO_ORDER_LINE_ID = UUID("21000000-0000-4000-8000-000000000001")
DEMO_RECEIPT_ID = UUID("30000000-0000-4000-8000-000000000001")
DEMO_RECEIPT_LINE_ID = UUID("31000000-0000-4000-8000-000000000001")
DEMO_INVOICE_ID = UUID("40000000-0000-4000-8000-000000000001")
DEMO_INVOICE_LINE_ID = UUID("41000000-0000-4000-8000-000000000001")


class SeedConflict(RuntimeError):
    pass


def _ensure_record(session: Session, expected, natural_key):
    """Compare global fixed IDs and scoped keys; never adopt or update a row."""
    model = type(expected)
    # Timestamps are server-generated on insertion, not the illustrative dates
    # in blueprint responses. Existing timestamps must never be replaced.
    values = {column.key: getattr(expected, column.key) for column in inspect(model).column_attrs if column.key != "created_at"}
    matches = list(session.scalars(select(model).where(or_(model.id == expected.id, natural_key)).execution_options(populate_existing=True)))
    if matches:
        if len(matches) != 1 or any(getattr(matches[0], key) != value for key, value in values.items()):
            raise SeedConflict(f"Demo {model.__tablename__} ID, identifier, or values conflict; nothing was overwritten.")
        return matches[0]
    # Copy only column values. Child rows are ensured separately so an existing
    # header can gain its missing expected line without cascading duplicate rows.
    saved = model(**values)
    session.add(saved)
    session.flush()
    return saved


def _ensure_document(session: Session, expected, natural_key, line_model, parent_field: str, line_id: UUID):
    expected.lines[0].id = line_id
    setattr(expected.lines[0], parent_field, expected.id)
    # Order-line ownership on priced orders is copied at flush by the ORM for
    # ordinary creates; this explicit seed projection needs it before that flush.
    if isinstance(expected, PurchaseOrder):
        expected.lines[0].purchase_order_id = expected.id
    saved = _ensure_record(session, expected, natural_key)
    parent_column = getattr(line_model, parent_field)
    if session.scalar(select(line_model.id).where(parent_column == saved.id, line_model.id != line_id).limit(1)) is not None:
        raise SeedConflict(f"Demo {line_model.__tablename__} contains unexpected lines; nothing was overwritten.")
    _ensure_record(session, expected.lines[0], and_(
        line_model.workspace_id == DEMO_WORKSPACE_ID, parent_column == saved.id, line_model.line_no == 1,
    ))
    session.expire(saved, ["lines"])
    return saved


def ensure_demo_records(session: Session) -> None:
    """Insert/verify the complete fixture without committing; caller owns rollback."""
    ensure_demo_workspace(session)
    supplier = manual_records.build_supplier(DEMO_WORKSPACE_ID, SupplierCreate.model_validate({
        "supplier_code": "DEMO-OFFICE-001", "name": "Demo Office Supplies",
        "notes": "Fictional supplier for the local demonstration.",
    }))
    supplier.id = DEMO_SUPPLIER_ID
    _ensure_record(session, supplier, and_(Supplier.workspace_id == DEMO_WORKSPACE_ID, Supplier.supplier_code == supplier.supplier_code))

    order = manual_records.build_purchase_order(session, DEMO_WORKSPACE_ID, PurchaseOrderCreate.model_validate({
        "supplier_id": str(DEMO_SUPPLIER_ID), "po_number": "PO-DEMO-001", "order_date": "2026-10-13", "currency": "EUR",
        "lines": [{"description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000"}],
    }))
    order.id = DEMO_ORDER_ID
    _ensure_document(session, order, and_(PurchaseOrder.workspace_id == DEMO_WORKSPACE_ID, PurchaseOrder.po_number == order.po_number), PurchaseOrderLine, "purchase_order_id", DEMO_ORDER_LINE_ID)

    receipt = manual_records.build_delivery_receipt(session, DEMO_WORKSPACE_ID, DeliveryReceiptCreate.model_validate({
        "purchase_order_id": str(DEMO_ORDER_ID), "receipt_number": "DR-DEMO-001", "received_date": "2026-10-14",
        "lines": [{"purchase_order_line_id": str(DEMO_ORDER_LINE_ID), "quantity_received": "8.000"}],
    }))
    receipt.id = DEMO_RECEIPT_ID
    _ensure_document(session, receipt, and_(DeliveryReceipt.workspace_id == DEMO_WORKSPACE_ID, DeliveryReceipt.receipt_number == receipt.receipt_number), DeliveryReceiptLine, "delivery_receipt_id", DEMO_RECEIPT_LINE_ID)

    invoice = manual_records.build_invoice(session, DEMO_WORKSPACE_ID, InvoiceCreate.model_validate({
        "supplier_id": str(DEMO_SUPPLIER_ID), "purchase_order_id": str(DEMO_ORDER_ID), "invoice_number": "INV-DEMO-001",
        "invoice_date": "2026-10-15", "due_date": "2026-11-14", "currency": "EUR", "tax_amount": "0.00",
        "lines": [{"description": "Keyboard", "quantity": "10.000", "unit_price": "25.0000", "purchase_order_line_id": str(DEMO_ORDER_LINE_ID)}],
    }))
    invoice.id = DEMO_INVOICE_ID
    _ensure_document(session, invoice, and_(Invoice.workspace_id == DEMO_WORKSPACE_ID, Invoice.supplier_id == DEMO_SUPPLIER_ID, Invoice.invoice_number == invoice.invoice_number), InvoiceLine, "invoice_id", DEMO_INVOICE_LINE_ID)


def initialize_demo(session: Session) -> None:
    try:
        ensure_demo_records(session)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise SeedConflict("Demo IDs or identifiers conflicted during insertion; nothing was overwritten.") from None
    except BaseException:
        session.rollback()
        raise


def main() -> int:
    try:
        with SessionLocal() as session:
            initialize_demo(session)
        print("Fictional demo ready: DEMO-OFFICE-001, PO-DEMO-001 (10), DR-DEMO-001 (8), INV-DEMO-001 (10, EUR 250.00, draft).")
        return 0
    except (SeedConflict, WorkspaceConflict) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Demo initialization failed; check PostgreSQL and apply migrations first. No partial seed was saved.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
