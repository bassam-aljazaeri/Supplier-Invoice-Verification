from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import SessionDependency, WorkspaceDependency
from app.api.errors import BusinessRoute
from app.models import DeliveryReceipt
from app.schemas.delivery_receipt import (
    DeliveryReceiptCreate, DeliveryReceiptList, DeliveryReceiptQuery, DeliveryReceiptRead,
)
from app.services import manual_records

router = APIRouter(prefix="/delivery-receipts", tags=["Delivery receipts"], route_class=BusinessRoute)


@router.post("", response_model=DeliveryReceiptRead, status_code=201)
def create_delivery_receipt(payload: DeliveryReceiptCreate, response: Response, session: SessionDependency, workspace_id: WorkspaceDependency):
    saved = manual_records.create_delivery_receipt(session, workspace_id, payload)
    response.headers["Location"] = f"/delivery-receipts/{saved.id}"
    return saved


@router.get("", response_model=DeliveryReceiptList)
def list_delivery_receipts(params: Annotated[DeliveryReceiptQuery, Query()], session: SessionDependency, workspace_id: WorkspaceDependency):
    filters = () if params.purchase_order_id is None else (DeliveryReceipt.purchase_order_id == params.purchase_order_id,)
    rows, total = manual_records.list_records(session, DeliveryReceipt, workspace_id, params.limit, params.offset, *filters)
    return DeliveryReceiptList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.get("/{id}", response_model=DeliveryReceiptRead)
def retrieve_delivery_receipt(id: UUID, session: SessionDependency, workspace_id: WorkspaceDependency):
    return DeliveryReceiptRead.model_validate(manual_records.get_delivery_receipt(session, workspace_id, id))
