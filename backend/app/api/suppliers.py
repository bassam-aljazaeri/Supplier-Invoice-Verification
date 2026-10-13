from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import SessionDependency, WorkspaceDependency
from app.api.errors import BusinessRoute
from app.models import Supplier
from app.schemas.common import Pagination
from app.schemas.supplier import SupplierCreate, SupplierList, SupplierRead
from app.services import manual_records

router = APIRouter(prefix="/suppliers", tags=["Suppliers"], route_class=BusinessRoute)


@router.post("", response_model=SupplierRead, status_code=201)
def create_supplier(payload: SupplierCreate, response: Response, session: SessionDependency, workspace_id: WorkspaceDependency):
    saved = manual_records.create_supplier(session, workspace_id, payload)
    response.headers["Location"] = f"/suppliers/{saved.id}"
    return saved


@router.get("", response_model=SupplierList)
def list_suppliers(params: Annotated[Pagination, Query()], session: SessionDependency, workspace_id: WorkspaceDependency):
    rows, total = manual_records.list_records(session, Supplier, workspace_id, params.limit, params.offset)
    return SupplierList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.get("/{id}", response_model=SupplierRead)
def retrieve_supplier(id: UUID, session: SessionDependency, workspace_id: WorkspaceDependency):
    return SupplierRead.model_validate(manual_records.get_supplier(session, workspace_id, id))
