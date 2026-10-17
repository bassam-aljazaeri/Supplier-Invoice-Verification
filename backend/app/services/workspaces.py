"""Workspace discovery and atomic creation; authorization is owned by the boundary."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.errors import BusinessError, forbidden
from app.models import Workspace, WorkspaceMembership
from app.schemas.membership import MembershipRead, WorkspaceCreated
from app.schemas.workspace import AccessibleWorkspace, WorkspaceRead
from app.services.memberships import MembershipNotFound, ensure_membership


def accessible_workspaces(session, user_id, limit, offset):
    conditions = WorkspaceMembership.application_user_id == user_id
    total = session.scalar(select(func.count()).select_from(WorkspaceMembership).where(conditions))
    rows = session.execute(select(Workspace, WorkspaceMembership.role).join(
        WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id,
    ).where(conditions).order_by(Workspace.created_at.desc(), Workspace.id.desc()).limit(limit).offset(offset))
    return [AccessibleWorkspace(**WorkspaceRead.model_validate(workspace).model_dump(), role=role) for workspace, role in rows], total


def create_workspace(session, user_id, payload):
    try:
        workspace = Workspace(slug=payload.slug, name=payload.name)
        session.add(workspace)
        session.flush()
        membership = ensure_membership(session, workspace.id, user_id, "administrator")
        result = WorkspaceCreated(workspace=WorkspaceRead.model_validate(workspace), membership=MembershipRead.model_validate(membership))
        session.commit()
        return result
    except MembershipNotFound:
        session.rollback()
        raise forbidden() from None
    except IntegrityError as error:
        session.rollback()
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_workspaces_slug":
            raise BusinessError(409, "conflict", "This workspace slug is already in use.") from None
        raise
    except BaseException:
        session.rollback()
        raise
