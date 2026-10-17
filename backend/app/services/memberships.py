"""Trusted persistence operations, not HTTP authorization. Caller owns transaction.

Never commit or roll back here. Callers must roll back on any failure and keep
the workspace lock until commit. Future HTTP callers must also check their own
administrator authority after acquiring that lock. No router uses this yet.
"""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import ApplicationUser, MembershipRole, Workspace, WorkspaceMembership


class MembershipError(RuntimeError):
    pass


class MembershipNotFound(MembershipError):
    pass


class MembershipConflict(MembershipError):
    pass


def validate_role(role: str) -> None:
    if role not in set(MembershipRole):
        raise MembershipError("Use administrator, accountant, or approver as the role.")


def lock_workspace(session: Session, *, workspace_id: UUID | None = None, workspace_slug: str | None = None) -> Workspace:
    """Serialize access mutations using the stable workspace row, including adds."""
    if (workspace_id is None) == (workspace_slug is None):
        raise MembershipError("Choose exactly one workspace identifier.")
    with session.no_autoflush:
        # READ COMMITTED gives each post-lock query a fresh committed snapshot.
        if session.connection().get_isolation_level() != "READ COMMITTED":
            raise MembershipError("Membership changes require READ COMMITTED isolation.")
        session.execute(text("SET LOCAL lock_timeout = '3s'"))
        condition = Workspace.id == workspace_id if workspace_id is not None else Workspace.slug == workspace_slug
        workspace = session.scalar(select(Workspace).where(condition).with_for_update().execution_options(populate_existing=True))
    if workspace is None:
        raise MembershipNotFound("The workspace does not exist; initialize it explicitly first.")
    return workspace


def _lock_user(session: Session, application_user_id: UUID, *, require_active: bool = True) -> ApplicationUser:
    user = session.scalar(select(ApplicationUser).where(
        ApplicationUser.id == application_user_id,
    ).with_for_update().execution_options(populate_existing=True))
    if user is None or (require_active and not user.is_active):
        raise MembershipNotFound("The application user is missing or inactive.")
    return user


def get_membership(session: Session, workspace_id: UUID, application_user_id: UUID) -> WorkspaceMembership | None:
    return session.scalar(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.application_user_id == application_user_id,
    ).execution_options(populate_existing=True))


def list_memberships(session: Session, workspace_id: UUID) -> list[WorkspaceMembership]:
    return list(session.scalars(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
    ).order_by(WorkspaceMembership.created_at.desc(), WorkspaceMembership.id.desc())))


def ensure_membership(session: Session, workspace_id: UUID, application_user_id: UUID, role: str) -> WorkspaceMembership:
    """Add or verify an identical assignment; a different role is a conflict."""
    validate_role(role)
    lock_workspace(session, workspace_id=workspace_id)
    _lock_user(session, application_user_id)
    membership = get_membership(session, workspace_id, application_user_id)
    if membership is not None:
        if membership.role != role:
            raise MembershipConflict("A different membership role already exists; nothing was replaced.")
        return membership
    membership = WorkspaceMembership(workspace_id=workspace_id, application_user_id=application_user_id, role=role)
    session.add(membership)
    session.flush()
    return membership


def _protect_last_administrator(session: Session, membership: WorkspaceMembership, user: ApplicationUser) -> None:
    if membership.role == MembershipRole.ADMINISTRATOR and user.is_active:
        administrators = session.scalar(select(func.count()).select_from(WorkspaceMembership).join(
            ApplicationUser, ApplicationUser.id == WorkspaceMembership.application_user_id,
        ).where(
            WorkspaceMembership.workspace_id == membership.workspace_id,
            WorkspaceMembership.role == MembershipRole.ADMINISTRATOR,
            ApplicationUser.is_active.is_(True),
        ))
        if administrators <= 1:
            raise MembershipConflict("The last active administrator cannot be removed or demoted.")


def change_membership_role(session: Session, workspace_id: UUID, application_user_id: UUID, role: str) -> WorkspaceMembership:
    validate_role(role)
    lock_workspace(session, workspace_id=workspace_id)
    user = _lock_user(session, application_user_id)
    membership = get_membership(session, workspace_id, application_user_id)
    if membership is None:
        raise MembershipNotFound("The membership does not exist.")
    if membership.role != role:
        _protect_last_administrator(session, membership, user)
        membership.role = role
        membership.updated_at = func.clock_timestamp()
        session.flush()
        session.refresh(membership)
    return membership


def remove_membership(session: Session, workspace_id: UUID, application_user_id: UUID) -> None:
    lock_workspace(session, workspace_id=workspace_id)
    user = _lock_user(session, application_user_id, require_active=False)
    membership = get_membership(session, workspace_id, application_user_id)
    if membership is None:
        raise MembershipNotFound("The membership does not exist.")
    _protect_last_administrator(session, membership, user)
    session.delete(membership)
    session.flush()
