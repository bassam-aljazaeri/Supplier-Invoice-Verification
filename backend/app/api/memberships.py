from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from app.api.dependencies import SessionDependency
from app.api.errors import BusinessError, MembershipRoute, missing
from app.models import WorkspaceMembership
from app.schemas.common import Pagination
from app.schemas.membership import MembershipCreate, MembershipList, MembershipRead, MembershipRoleChange
from app.services import memberships

router = APIRouter(prefix="/workspaces/{workspace_id}/memberships", tags=["Memberships"], route_class=MembershipRoute)


def conflict():
    return BusinessError(409, "conflict", "The membership change conflicts with an existing assignment or the last administrator rule.")


def save_membership(session, operation):
    try:
        result = operation()
        response = MembershipRead.model_validate(result) if result is not None else None
        session.commit()
        return response
    except memberships.MembershipNotFound:
        session.rollback()
        raise missing("membership or application user") from None
    except memberships.MembershipConflict:
        session.rollback()
        raise conflict() from None
    except BaseException:
        session.rollback()
        raise


@router.get("", response_model=MembershipList)
def list_memberships(params: Annotated[Pagination, Query()], session: SessionDependency, workspace_id: UUID):
    condition = WorkspaceMembership.workspace_id == workspace_id
    total = session.scalar(select(func.count()).select_from(WorkspaceMembership).where(condition))
    rows = session.scalars(select(WorkspaceMembership).where(condition).order_by(
        WorkspaceMembership.created_at.desc(), WorkspaceMembership.id.desc(),
    ).limit(params.limit).offset(params.offset))
    return MembershipList(items=[MembershipRead.model_validate(row) for row in rows], limit=params.limit, offset=params.offset, total=total)


@router.post("", response_model=MembershipRead, status_code=201)
def add_membership(payload: MembershipCreate, session: SessionDependency, workspace_id: UUID):
    def add():
        existing = memberships.get_membership(session, workspace_id, payload.application_user_id)
        # The service locks/rechecks user activity before resolving a duplicate.
        # Missing and inactive target users must share the same 404 contract.
        result = memberships.ensure_membership(session, workspace_id, payload.application_user_id, payload.role)
        if existing is not None:
            raise memberships.MembershipConflict()
        return result

    return save_membership(session, add)


@router.patch("/{application_user_id}", response_model=MembershipRead)
def change_membership(application_user_id: UUID, payload: MembershipRoleChange, session: SessionDependency, workspace_id: UUID):
    return save_membership(session, lambda: memberships.change_membership_role(session, workspace_id, application_user_id, payload.role))


@router.delete("/{application_user_id}", status_code=204)
def remove_membership(application_user_id: UUID, session: SessionDependency, workspace_id: UUID):
    save_membership(session, lambda: memberships.remove_membership(session, workspace_id, application_user_id))
    return Response(status_code=204)
