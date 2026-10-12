from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.errors import BusinessError, invalid, missing
from app.models import PurchaseOrder, PurchaseOrderLine, Supplier
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderRead
from app.schemas.supplier import SupplierCreate, SupplierRead
from app.services.money import MoneyError, calculate_line_total, sum_line_totals


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
        }
        if constraint in conflicts:
            field, message = conflicts[constraint]
            raise BusinessError(409, "conflict", "A record with this identifier already exists.", [{"field": field, "message": message}]) from None
        if constraint == "fk_purchase_orders_supplier":
            raise missing("supplier", "supplier_id") from None
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
    return save_record(session, Supplier(workspace_id=workspace_id, **payload.model_dump()), SupplierRead)


def create_purchase_order(session: Session, workspace_id: UUID, payload: PurchaseOrderCreate) -> PurchaseOrderRead:
    get_supplier(session, workspace_id, payload.supplier_id, field="supplier_id")
    amounts = []
    for index, line in enumerate(payload.lines):
        try:
            amounts.append(calculate_line_total(line.quantity, line.unit_price))
        except MoneyError as error:
            raise invalid(f"lines[{index}]", str(error)) from None
    try:
        subtotal = sum_line_totals(amounts)
    except MoneyError as error:
        raise invalid("lines", str(error)) from None
    order = PurchaseOrder(
        workspace_id=workspace_id, supplier_id=payload.supplier_id,
        po_number=payload.po_number, order_date=payload.order_date,
        currency=payload.currency, notes=payload.notes, subtotal=subtotal,
        lines=[PurchaseOrderLine(
            workspace_id=workspace_id, line_no=index + 1, description=line.description,
            quantity=line.quantity, unit_price=line.unit_price, line_total=amounts[index],
        ) for index, line in enumerate(payload.lines)],
    )
    return save_record(session, order, PurchaseOrderRead)


def list_records(session: Session, model, workspace_id: UUID, limit: int, offset: int, *filters):
    conditions = (model.workspace_id == workspace_id, *filters)
    total = session.scalar(select(func.count()).select_from(model).where(*conditions))
    rows = list(session.scalars(select(model).where(*conditions).order_by(
        model.created_at.desc(), model.id.desc(),
    ).offset(offset).limit(limit)))
    return rows, total


def get_purchase_order(session: Session, workspace_id: UUID, order_id: UUID) -> PurchaseOrder:
    order = session.scalar(select(PurchaseOrder).where(
        PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.id == order_id,
    ).options(selectinload(PurchaseOrder.lines)))
    if order is None:
        raise missing("purchase order")
    return order
