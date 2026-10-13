from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import SessionDependency, WorkspaceDependency
from app.api.errors import BusinessRoute
from app.models import PurchaseOrder
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderList, PurchaseOrderQuery, PurchaseOrderRead
from app.services import manual_records

router = APIRouter(prefix="/purchase-orders", tags=["Purchase orders"], route_class=BusinessRoute)


@router.post("", response_model=PurchaseOrderRead, status_code=201)
def create_purchase_order(payload: PurchaseOrderCreate, response: Response, session: SessionDependency, workspace_id: WorkspaceDependency):
    saved = manual_records.create_purchase_order(session, workspace_id, payload)
    response.headers["Location"] = f"/purchase-orders/{saved.id}"
    return saved


@router.get("", response_model=PurchaseOrderList)
def list_purchase_orders(params: Annotated[PurchaseOrderQuery, Query()], session: SessionDependency, workspace_id: WorkspaceDependency):
    filters = () if params.supplier_id is None else (PurchaseOrder.supplier_id == params.supplier_id,)
    rows, total = manual_records.list_records(session, PurchaseOrder, workspace_id, params.limit, params.offset, *filters)
    return PurchaseOrderList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.get("/{id}", response_model=PurchaseOrderRead)
def retrieve_purchase_order(id: UUID, session: SessionDependency, workspace_id: WorkspaceDependency):
    return PurchaseOrderRead.model_validate(manual_records.get_purchase_order(session, workspace_id, id))
