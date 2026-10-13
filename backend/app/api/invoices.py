from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import SessionDependency, WorkspaceDependency
from app.api.errors import BusinessRoute
from app.models import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceList, InvoiceQuery, InvoiceRead
from app.services import manual_records

router = APIRouter(prefix="/invoices", tags=["Draft invoices"], route_class=BusinessRoute)


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, response: Response, session: SessionDependency, workspace_id: WorkspaceDependency):
    saved = manual_records.create_invoice(session, workspace_id, payload)
    response.headers["Location"] = f"/invoices/{saved.id}"
    return saved


@router.get("", response_model=InvoiceList)
def list_invoices(params: Annotated[InvoiceQuery, Query()], session: SessionDependency, workspace_id: WorkspaceDependency):
    filters = []
    if params.supplier_id is not None:
        filters.append(Invoice.supplier_id == params.supplier_id)
    if params.purchase_order_id is not None:
        filters.append(Invoice.purchase_order_id == params.purchase_order_id)
    rows, total = manual_records.list_records(session, Invoice, workspace_id, params.limit, params.offset, *filters)
    return InvoiceList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.get("/{id}", response_model=InvoiceRead)
def retrieve_invoice(id: UUID, session: SessionDependency, workspace_id: WorkspaceDependency):
    return InvoiceRead.model_validate(manual_records.get_invoice(session, workspace_id, id))
