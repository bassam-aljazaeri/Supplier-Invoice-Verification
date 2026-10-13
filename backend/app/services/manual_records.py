from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.errors import BusinessError, invalid, missing
from app.models import (
    DeliveryReceipt, DeliveryReceiptLine, Invoice, InvoiceLine, PurchaseOrder,
    PurchaseOrderLine, Supplier,
)
from app.schemas.delivery_receipt import DeliveryReceiptCreate, DeliveryReceiptRead
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderRead
from app.schemas.supplier import SupplierCreate, SupplierRead
from app.services.money import MoneyError, calculate_invoice_total, calculate_line_total, sum_line_totals


def save_record(session: Session, record, read_schema):
    try:
        session.add(record)
        session.flush()
        # Validate/materialize all response fields while rollback is still possible.
        result = read_schema.model_validate(record)
        session.commit()
        return result
    except IntegrityError as error:
        session.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        conflicts = {
            "uq_suppliers_code": ("supplier_code", "This supplier code is already in use."),
            "uq_purchase_orders_number": ("po_number", "This purchase-order number is already in use."),
            "uq_delivery_receipts_number": ("receipt_number", "This delivery-receipt number is already in use."),
            "uq_invoices_supplier_number": ("invoice_number", "This invoice number is already in use for the supplier."),
        }
        if constraint in conflicts:
            field, message = conflicts[constraint]
            raise BusinessError(409, "conflict", "A record with this identifier already exists.", [{"field": field, "message": message}]) from None
        if constraint in {"fk_purchase_orders_supplier", "fk_invoices_supplier"}:
            raise missing("supplier", "supplier_id") from None
        if constraint in {"fk_delivery_receipts_order", "fk_invoices_supplier_order"}:
            raise missing("purchase order", "purchase_order_id") from None
        if constraint in {"fk_receipt_lines_order_line", "fk_invoice_lines_order_line"}:
            raise missing("purchase-order line", "lines") from None
        raise
    except BaseException:
        session.rollback()
        raise


def get_supplier(session: Session, workspace_id: UUID, supplier_id: UUID, *, field: str = "id") -> Supplier:
    supplier = session.scalar(select(Supplier).where(
        Supplier.workspace_id == workspace_id, Supplier.id == supplier_id,
    ))
    if supplier is None:
        raise missing("supplier", field)
    return supplier


def create_supplier(session: Session, workspace_id: UUID, payload: SupplierCreate) -> SupplierRead:
    return save_record(session, build_supplier(workspace_id, payload), SupplierRead)


def build_supplier(workspace_id: UUID, payload: SupplierCreate) -> Supplier:
    return Supplier(workspace_id=workspace_id, **payload.model_dump())


def create_purchase_order(session: Session, workspace_id: UUID, payload: PurchaseOrderCreate) -> PurchaseOrderRead:
    return save_record(session, build_purchase_order(session, workspace_id, payload), PurchaseOrderRead)


def build_purchase_order(session: Session, workspace_id: UUID, payload: PurchaseOrderCreate) -> PurchaseOrder:
    """Validate and build; the caller owns persistence and its transaction."""
    get_supplier(session, workspace_id, payload.supplier_id, field="supplier_id")
    amounts, subtotal = calculate_priced_lines(payload.lines)
    order = PurchaseOrder(
        workspace_id=workspace_id, supplier_id=payload.supplier_id,
        po_number=payload.po_number, order_date=payload.order_date,
        currency=payload.currency, notes=payload.notes, subtotal=subtotal,
        lines=[PurchaseOrderLine(
            workspace_id=workspace_id, line_no=index + 1, description=line.description,
            quantity=line.quantity, unit_price=line.unit_price, line_total=amounts[index],
        ) for index, line in enumerate(payload.lines)],
    )
    return order


def calculate_priced_lines(lines):
    amounts = []
    for index, line in enumerate(lines):
        try:
            amounts.append(calculate_line_total(line.quantity, line.unit_price))
        except MoneyError as error:
            raise invalid(f"lines[{index}]", str(error)) from None
    try:
        subtotal = sum_line_totals(amounts)
    except MoneyError as error:
        raise invalid("lines", str(error)) from None
    return amounts, subtotal


def list_records(session: Session, model, workspace_id: UUID, limit: int, offset: int, *filters):
    conditions = (model.workspace_id == workspace_id, *filters)
    total = session.scalar(select(func.count()).select_from(model).where(*conditions))
    rows = list(session.scalars(select(model).where(*conditions).order_by(
        model.created_at.desc(), model.id.desc(),
    ).offset(offset).limit(limit)))
    return rows, total


def get_purchase_order(session: Session, workspace_id: UUID, order_id: UUID, *, field: str = "id") -> PurchaseOrder:
    order = session.scalar(select(PurchaseOrder).where(
        PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.id == order_id,
    ).options(selectinload(PurchaseOrder.lines)))
    if order is None:
        raise missing("purchase order", field)
    return order


def validate_order_line(session: Session, workspace_id: UUID, order_id: UUID, line_id: UUID, field: str):
    line = session.scalar(select(PurchaseOrderLine).where(
        PurchaseOrderLine.workspace_id == workspace_id, PurchaseOrderLine.id == line_id,
    ))
    if line is None:
        raise missing("purchase-order line", field)
    if line.purchase_order_id != order_id:
        raise invalid(field, "Choose a line from the selected purchase order.")


def create_delivery_receipt(session: Session, workspace_id: UUID, payload: DeliveryReceiptCreate) -> DeliveryReceiptRead:
    return save_record(session, build_delivery_receipt(session, workspace_id, payload), DeliveryReceiptRead)


def build_delivery_receipt(session: Session, workspace_id: UUID, payload: DeliveryReceiptCreate) -> DeliveryReceipt:
    order = get_purchase_order(session, workspace_id, payload.purchase_order_id, field="purchase_order_id")
    seen = set()
    for index, line in enumerate(payload.lines):
        field = f"lines[{index}].purchase_order_line_id"
        if line.purchase_order_line_id in seen:
            raise invalid(field, "An order line may appear only once in a delivery receipt.")
        seen.add(line.purchase_order_line_id)
        validate_order_line(session, workspace_id, order.id, line.purchase_order_line_id, field)
    receipt = DeliveryReceipt(
        workspace_id=workspace_id, purchase_order_id=order.id,
        receipt_number=payload.receipt_number, received_date=payload.received_date, notes=payload.notes,
        lines=[DeliveryReceiptLine(
            workspace_id=workspace_id, purchase_order_id=order.id, line_no=index + 1,
            purchase_order_line_id=line.purchase_order_line_id, quantity_received=line.quantity_received,
        ) for index, line in enumerate(payload.lines)],
    )
    return receipt


def create_invoice(session: Session, workspace_id: UUID, payload: InvoiceCreate) -> InvoiceRead:
    return save_record(session, build_invoice(session, workspace_id, payload), InvoiceRead)


def build_invoice(session: Session, workspace_id: UUID, payload: InvoiceCreate) -> Invoice:
    get_supplier(session, workspace_id, payload.supplier_id, field="supplier_id")
    if payload.purchase_order_id is not None:
        order = get_purchase_order(session, workspace_id, payload.purchase_order_id, field="purchase_order_id")
        if order.supplier_id != payload.supplier_id:
            raise invalid("purchase_order_id", "Choose a purchase order belonging to the selected supplier.")
    for index, line in enumerate(payload.lines):
        if line.purchase_order_line_id is not None:
            field = f"lines[{index}].purchase_order_line_id"
            if payload.purchase_order_id is None:
                raise invalid(field, "Select a purchase order before mapping invoice lines.")
            validate_order_line(session, workspace_id, payload.purchase_order_id, line.purchase_order_line_id, field)
    amounts, subtotal = calculate_priced_lines(payload.lines)
    try:
        total = calculate_invoice_total(subtotal, payload.tax_amount)
    except MoneyError as error:
        raise invalid("tax_amount", str(error)) from None
    invoice = Invoice(
        workspace_id=workspace_id, supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id, invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date, due_date=payload.due_date, currency=payload.currency,
        status="draft", notes=payload.notes, subtotal=subtotal, tax_amount=payload.tax_amount, total=total,
        lines=[InvoiceLine(
            workspace_id=workspace_id, line_no=index + 1, description=line.description,
            quantity=line.quantity, unit_price=line.unit_price, line_total=amounts[index],
            purchase_order_line_id=line.purchase_order_line_id,
            purchase_order_id=payload.purchase_order_id if line.purchase_order_line_id is not None else None,
        ) for index, line in enumerate(payload.lines)],
    )
    return invoice


def get_delivery_receipt(session: Session, workspace_id: UUID, receipt_id: UUID) -> DeliveryReceipt:
    receipt = session.scalar(select(DeliveryReceipt).where(
        DeliveryReceipt.workspace_id == workspace_id, DeliveryReceipt.id == receipt_id,
    ).options(selectinload(DeliveryReceipt.lines)))
    if receipt is None:
        raise missing("delivery receipt")
    return receipt


def get_invoice(session: Session, workspace_id: UUID, invoice_id: UUID) -> Invoice:
    invoice = session.scalar(select(Invoice).where(
        Invoice.workspace_id == workspace_id, Invoice.id == invoice_id,
    ).options(selectinload(Invoice.lines)))
    if invoice is None:
        raise missing("invoice")
    return invoice
