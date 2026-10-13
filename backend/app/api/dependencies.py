from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.errors import unavailable
from app.db import get_session
from app.models import Workspace
from app.workspace import DEMO_WORKSPACE_ID, is_demo_workspace

SessionDependency = Annotated[Session, Depends(get_session)]


def get_demo_workspace_id(session: SessionDependency) -> UUID:
    workspace = session.get(Workspace, DEMO_WORKSPACE_ID)
    if workspace is None or not is_demo_workspace(workspace):
        raise unavailable()
    return workspace.id


WorkspaceDependency = Annotated[UUID, Depends(get_demo_workspace_id)]
