from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.dependencies import SessionDependency, UserDependency
from app.api.errors import AccountRoute
from app.models import Workspace, WorkspaceMembership
from app.schemas.identity import ApplicationUserRead, MeRead
from app.schemas.membership import OwnMembership

router = APIRouter(tags=["Current identity"], route_class=AccountRoute)


@router.get("/me", response_model=MeRead)
def me(session: SessionDependency, user: UserDependency):
    rows = session.scalars(select(WorkspaceMembership).join(Workspace).where(
        WorkspaceMembership.application_user_id == user.id,
    ).options(joinedload(WorkspaceMembership.workspace)).order_by(Workspace.created_at.desc(), Workspace.id.desc()))
    result = MeRead(user=ApplicationUserRead.model_validate(user), memberships=[OwnMembership.model_validate(row) for row in rows])
    session.commit()
    return result
