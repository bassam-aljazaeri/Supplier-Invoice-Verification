from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import SessionDependency, UserDependency
from app.api.errors import AccountRoute
from app.schemas.common import Pagination
from app.schemas.membership import WorkspaceCreated
from app.schemas.workspace import WorkspaceCreate, WorkspaceList
from app.services import workspaces

router = APIRouter(prefix="/workspaces", tags=["Workspaces"], route_class=AccountRoute)


@router.get("", response_model=WorkspaceList)
def list_workspaces(params: Annotated[Pagination, Query()], session: SessionDependency, user: UserDependency):
    rows, total = workspaces.accessible_workspaces(session, user.id, params.limit, params.offset)
    return WorkspaceList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.post("", response_model=WorkspaceCreated, status_code=201)
def create_workspace(payload: WorkspaceCreate, session: SessionDependency, user: UserDependency):
    return workspaces.create_workspace(session, user.id, payload)
