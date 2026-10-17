from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.models import ApplicationUser


def request_session(request: Request) -> Session:
    return request.state.db_session


def current_user(request: Request) -> ApplicationUser:
    return request.state.application_user


def authorized_workspace(request: Request) -> UUID:
    return request.state.workspace_id


SessionDependency = Annotated[Session, Depends(request_session)]
UserDependency = Annotated[ApplicationUser, Depends(current_user)]
WorkspaceDependency = Annotated[UUID, Depends(authorized_workspace)]
