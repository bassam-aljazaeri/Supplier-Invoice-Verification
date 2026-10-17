"""Protected-route boundary: verified identity, one session, current DB authority."""

from contextlib import asynccontextmanager, contextmanager
from uuid import UUID

from fastapi import Request
from fastapi.concurrency import contextmanager_in_threadpool, run_in_threadpool
from sqlalchemy import select

from app.auth import InvalidCredentials, JwksUnavailable, bearer_token
from app.api.errors import forbidden, invalid, unauthorized, unavailable
from app.db import get_session
from app.models import ApplicationUser
from app.services.identity import IdentityError, ensure_application_user
from app.services.memberships import MembershipNotFound, get_membership, lock_workspace


def workspace_uuid(value: str) -> UUID:
    try:
        result = UUID(value)
        if str(result) != value:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise invalid("workspace_id", "Choose one workspace using a canonical UUID.") from None


def resolve_authority(request: Request, session, identity, mode: str) -> None:
    user = session.scalar(select(ApplicationUser).where(
        ApplicationUser.issuer == identity.issuer, ApplicationUser.subject == identity.subject,
    ).execution_options(populate_existing=True))
    if user is None and request.url.path == "/me" and request.method == "GET":
        try:
            user = ensure_application_user(session, identity.issuer, identity.subject)
        except IdentityError:
            raise forbidden() from None
    if user is None or not user.is_active:
        raise forbidden()
    request.state.application_user = user
    selected = request.headers.getlist("x-workspace-id")
    if mode == "business":
        if len(selected) != 1:
            raise invalid("workspace_id", "Choose one workspace using X-Workspace-ID.")
        workspace_id = workspace_uuid(selected[0])
    else:
        if selected:
            raise invalid("workspace_id", "X-Workspace-ID is not allowed on this endpoint.")
        if mode == "none":
            return
        workspace_id = workspace_uuid(request.path_params["workspace_id"])
        if request.method != "GET":
            try:
                lock_workspace(session, workspace_id=workspace_id)
            except MembershipNotFound:
                raise forbidden() from None
            # Authority may have changed while the workspace lock was held elsewhere.
            session.refresh(user)
            if not user.is_active:
                raise forbidden()
    membership = get_membership(session, workspace_id, user.id)
    if membership is None:
        raise forbidden()
    if mode == "path" and membership.role != "administrator":
        raise forbidden()
    if mode == "business" and request.method != "GET" and membership.role not in {"administrator", "accountant"}:
        raise forbidden()
    request.state.workspace_id = workspace_id


@asynccontextmanager
async def authorized_request(request: Request, mode: str):
    try:
        token = bearer_token(request.headers.getlist("authorization"))
        verifier = getattr(request.app.state, "token_verifier", None)
        if verifier is None:
            raise unavailable()
        identity = await verifier.verify(token)
    except InvalidCredentials:
        raise unauthorized() from None
    except JwksUnavailable:
        raise unavailable() from None
    # Use the same override point as FastAPI, retaining the guarded fixture's
    # rollback/close behavior. Dependencies below reuse this exact session.
    factory = request.app.dependency_overrides.get(get_session, get_session)
    async with contextmanager_in_threadpool(contextmanager(factory)()) as session:
        request.state.db_session = session
        await run_in_threadpool(resolve_authority, request, session, identity, mode)
        yield
