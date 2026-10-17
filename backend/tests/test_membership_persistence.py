"""Persistence and real PostgreSQL lock races, only on the guarded test target."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from queue import Queue
import time
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, configure_mappers

from app.bootstrap_membership import bootstrap_membership
from app.models import ApplicationUser, Workspace, WorkspaceMembership
from app.services.identity import IdentityError, ensure_application_user
from app.services.memberships import (
    MembershipConflict, MembershipError, MembershipNotFound, change_membership_role,
    ensure_membership, get_membership, list_memberships, lock_workspace, remove_membership,
)

pytestmark = pytest.mark.postgres
ISSUER = "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE"


@pytest.fixture
def membership_graph(schema_session):
    workspace = Workspace(slug="membership-a", name="Synthetic membership workspace")
    other = Workspace(slug="membership-b", name="Synthetic other workspace")
    schema_session.add_all([workspace, other])
    schema_session.flush()
    users = [ensure_application_user(schema_session, ISSUER, f"synthetic-{index}") for index in range(3)]
    ensure_membership(schema_session, workspace.id, users[0].id, "administrator")
    ensure_membership(schema_session, other.id, users[1].id, "administrator")
    schema_session.commit()
    return workspace, other, users


def test_identity_uniqueness_is_exact_and_defaults_and_relationships_work(schema_session, membership_graph):
    workspace, other, users = membership_graph
    same = ensure_application_user(schema_session, ISSUER, "synthetic-0")
    assert same.id == users[0].id and same.is_active is True
    assert same.created_at.tzinfo is not None and same.updated_at.tzinfo is not None
    assert ensure_application_user(schema_session, ISSUER + "OTHER", "synthetic-0").id != same.id
    assert ensure_application_user(schema_session, ISSUER, "Synthetic-0").id != same.id
    membership = ensure_membership(schema_session, workspace.id, users[2].id, "accountant")
    ensure_membership(schema_session, other.id, users[2].id, "approver")
    configure_mappers()
    schema_session.expire_all()
    assert membership.workspace is workspace and membership.application_user is users[2]
    assert membership in workspace.memberships and membership in users[2].memberships
    assert membership.created_at.tzinfo is not None and membership.updated_at.tzinfo is not None
    assert {item.application_user_id for item in list_memberships(schema_session, workspace.id)} == {users[0].id, users[2].id}


@pytest.mark.parametrize(("model", "values", "constraint"), [
    (ApplicationUser, {"issuer": ISSUER, "subject": "synthetic-0"}, "uq_application_users_issuer_subject"),
    (ApplicationUser, {"issuer": "", "subject": "new"}, "ck_application_users_issuer_text"),
    (ApplicationUser, {"issuer": ISSUER, "subject": "\tnew"}, "ck_application_users_subject_text"),
    (WorkspaceMembership, {"role": "owner"}, "ck_workspace_memberships_role"),
    (WorkspaceMembership, {"role": "Administrator"}, "ck_workspace_memberships_role"),
    (WorkspaceMembership, {"role": "administrator"}, "uq_workspace_memberships_workspace_user"),
    (WorkspaceMembership, {"workspace_id": uuid4(), "role": "approver"}, "fk_workspace_memberships_workspace"),
    (WorkspaceMembership, {"application_user_id": uuid4(), "role": "approver"}, "fk_workspace_memberships_user"),
])
def test_named_database_constraints_reject_invalid_identity_and_membership(schema_session, membership_graph, model, values, constraint):
    workspace, _, users = membership_graph
    if model is WorkspaceMembership:
        values = {"workspace_id": workspace.id, "application_user_id": users[0].id, **values}
    with pytest.raises(IntegrityError) as error:
        with schema_session.begin_nested():
            schema_session.execute(insert(model).values(**values))
    assert error.value.orig.diag.constraint_name == constraint
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 2


@pytest.mark.parametrize("model", [ApplicationUser, Workspace])
def test_membership_foreign_keys_restrict_parent_deletion(schema_session, membership_graph, model):
    workspace, _, users = membership_graph
    record_id = workspace.id if model is Workspace else users[0].id
    with pytest.raises(IntegrityError):
        with schema_session.begin_nested():
            schema_session.execute(delete(model).where(model.id == record_id))


@pytest.mark.parametrize(("issuer", "subject"), [("", "subject"), (ISSUER, ""), (ISSUER, " subject"), (ISSUER, "s" * 256), ("i" * 513, "subject")])
def test_identity_validation_does_not_normalize_or_truncate(schema_session, issuer, subject):
    with pytest.raises(IdentityError):
        ensure_application_user(schema_session, issuer, subject)
    assert schema_session.scalar(select(func.count()).select_from(ApplicationUser)) == 0


def test_inactive_identity_is_never_reactivated(schema_session, membership_graph):
    _, _, users = membership_graph
    users[0].is_active = False
    schema_session.commit()
    with pytest.raises(IdentityError, match="inactive"):
        ensure_application_user(schema_session, ISSUER, users[0].subject)
    assert schema_session.get(ApplicationUser, users[0].id).is_active is False


def test_helpers_leave_transaction_ownership_to_caller(schema_session, membership_graph):
    workspace, _, users = membership_graph
    commits = []
    rollbacks = []
    event.listen(schema_session, "before_commit", lambda session: commits.append(True))
    event.listen(schema_session, "after_rollback", lambda session: rollbacks.append(True))
    new_user = ensure_application_user(schema_session, ISSUER, "uncommitted")
    new_id = new_user.id
    ensure_membership(schema_session, workspace.id, new_id, "approver")
    ensure_membership(schema_session, workspace.id, users[2].id, "accountant")
    change_membership_role(schema_session, workspace.id, users[2].id, "approver")
    remove_membership(schema_session, workspace.id, users[2].id)
    with pytest.raises(MembershipConflict):
        remove_membership(schema_session, workspace.id, users[0].id)
    assert commits == rollbacks == []
    schema_session.rollback()
    assert schema_session.get(ApplicationUser, new_id) is None
    assert get_membership(schema_session, workspace.id, users[2].id) is None
    assert get_membership(schema_session, workspace.id, users[0].id).role == "administrator"


def test_role_changes_update_only_updated_at_and_repeats_are_noops(schema_session, membership_graph):
    workspace, _, users = membership_graph
    membership = ensure_membership(schema_session, workspace.id, users[2].id, "accountant")
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    schema_session.execute(update(WorkspaceMembership).where(WorkspaceMembership.id == membership.id).values(updated_at=old))
    schema_session.commit()
    original_id, created_at = membership.id, membership.created_at
    changed = change_membership_role(schema_session, workspace.id, users[2].id, "approver")
    assert changed.updated_at > old
    updated_at = changed.updated_at
    assert changed.id == original_id and changed.created_at == created_at
    assert change_membership_role(schema_session, workspace.id, users[2].id, "approver").updated_at == updated_at
    assert ensure_membership(schema_session, workspace.id, users[2].id, "approver").updated_at == updated_at
    with pytest.raises(MembershipConflict):
        ensure_membership(schema_session, workspace.id, users[2].id, "accountant")


@pytest.mark.parametrize("action", ["remove", "accountant", "approver"])
def test_last_active_administrator_is_protected_and_other_workspace_does_not_count(schema_session, membership_graph, action):
    workspace, _, users = membership_graph
    # Even an administrator row for an inactive user cannot preserve access.
    ensure_membership(schema_session, workspace.id, users[1].id, "administrator")
    users[1].is_active = False
    schema_session.commit()
    with pytest.raises(MembershipConflict, match="last active administrator"):
        if action == "remove":
            remove_membership(schema_session, workspace.id, users[0].id)
        else:
            change_membership_role(schema_session, workspace.id, users[0].id, action)
    assert get_membership(schema_session, workspace.id, users[0].id).role == "administrator"


def test_another_active_administrator_allows_demotion_and_removal(schema_session, membership_graph):
    workspace, _, users = membership_graph
    ensure_membership(schema_session, workspace.id, users[1].id, "administrator")
    assert change_membership_role(schema_session, workspace.id, users[0].id, "accountant").role == "accountant"
    remove_membership(schema_session, workspace.id, users[0].id)
    schema_session.commit()
    assert get_membership(schema_session, workspace.id, users[0].id) is None
    assert get_membership(schema_session, workspace.id, users[1].id).role == "administrator"


def test_missing_workspace_user_membership_and_role_are_explicit(schema_session, membership_graph):
    workspace, _, users = membership_graph
    with pytest.raises(MembershipNotFound):
        ensure_membership(schema_session, uuid4(), users[0].id, "accountant")
    with pytest.raises(MembershipNotFound):
        ensure_membership(schema_session, workspace.id, uuid4(), "accountant")
    with pytest.raises(MembershipNotFound):
        remove_membership(schema_session, workspace.id, users[2].id)
    with pytest.raises(MembershipNotFound):
        change_membership_role(schema_session, workspace.id, users[2].id, "approver")
    with pytest.raises(MembershipError):
        ensure_membership(schema_session, workspace.id, users[2].id, "owner")


def wait_for_database_lock(engine, pid):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            # New transaction each time avoids a cached PostgreSQL stats snapshot.
            if connection.scalar(text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}) == "Lock":
                return
        time.sleep(0.01)
    raise AssertionError("Competing transaction did not wait on the expected database lock.")


@pytest.mark.parametrize(("first_action", "second_action"), [("remove", "remove"), ("demote", "demote"), ("remove", "demote"), ("demote", "remove")])
def test_concurrent_changes_leave_one_administrator(postgres_engine, committed_memberships, first_action, second_action):
    records = committed_memberships
    workspace_id = records["workspace_id"]
    first_id, second_id = records["user_ids"][:2]
    started = Queue()

    def mutate(session, user_id, action):
        if action == "remove":
            remove_membership(session, workspace_id, user_id)
        else:
            change_membership_role(session, workspace_id, user_id, "accountant")

    def competing_change():
        with Session(postgres_engine, expire_on_commit=False) as session:
            # Preload stale state deliberately; post-lock services must refresh it.
            assert get_membership(session, workspace_id, first_id).role == "administrator"
            started.put(session.scalar(text("SELECT pg_backend_pid()")))
            try:
                mutate(session, second_id, second_action)
                session.commit()
                return "unexpected-success"
            except MembershipConflict:
                session.rollback()
                return "last-admin-refused"

    with Session(postgres_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
        try:
            mutate(first, first_id, first_action)
            future = executor.submit(competing_change)
            wait_for_database_lock(postgres_engine, started.get(timeout=3))
            first.commit()
            assert future.result(timeout=6) == "last-admin-refused"
        finally:
            first.rollback()
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == "administrator",
        )) == 1
        assert get_membership(session, workspace_id, second_id).role == "administrator"


def test_lock_timeout_requires_rollback_and_later_request_recovers(postgres_engine, committed_memberships):
    records = committed_memberships
    with Session(postgres_engine) as first, Session(postgres_engine) as second:
        lock_workspace(first, workspace_id=records["workspace_id"])
        with pytest.raises(OperationalError) as error:
            remove_membership(second, records["workspace_id"], records["user_ids"][0])
        assert error.value.orig.sqlstate == "55P03"
        second.rollback()
        first.rollback()
        remove_membership(second, records["workspace_id"], records["user_ids"][0])
        second.rollback()
        assert get_membership(second, records["workspace_id"], records["user_ids"][0]) is not None


@pytest.mark.parametrize("other_role", ["accountant", "approver"])
def test_concurrent_bootstrap_keeps_first_role(postgres_engine, committed_memberships, other_role):
    records = committed_memberships
    subject = records["subjects"][2]
    started = Queue()

    def second_bootstrap():
        with Session(postgres_engine) as session:
            started.put(session.scalar(text("SELECT pg_backend_pid()")))
            with pytest.raises(MembershipConflict):
                bootstrap_membership(session, issuer=records["issuer"], subject=subject, workspace_slug=records["slug"], role=other_role)

    with Session(postgres_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
        try:
            ensure_membership(first, records["workspace_id"], records["user_ids"][2], "administrator")
            future = executor.submit(second_bootstrap)
            wait_for_database_lock(postgres_engine, started.get(timeout=3))
            first.commit()
            future.result(timeout=6)
        finally:
            first.rollback()
    with Session(postgres_engine) as session:
        assert get_membership(session, records["workspace_id"], records["user_ids"][2]).role == "administrator"


def test_concurrent_first_identity_registration_returns_one_user(postgres_engine, committed_memberships):
    records = committed_memberships
    subject = "identity-race-" + uuid4().hex
    records["subjects"].append(subject)
    started = Queue()

    def competing_registration():
        with Session(postgres_engine) as session:
            started.put(session.scalar(text("SELECT pg_backend_pid()")))
            user = ensure_application_user(session, records["issuer"], subject)
            user_id = user.id
            session.commit()
            return user_id

    with Session(postgres_engine) as first, ThreadPoolExecutor(max_workers=1) as executor:
        try:
            user_id = ensure_application_user(first, records["issuer"], subject).id
            future = executor.submit(competing_registration)
            wait_for_database_lock(postgres_engine, started.get(timeout=3))
            first.commit()
            assert future.result(timeout=6) == user_id
        finally:
            first.rollback()
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(ApplicationUser).where(
            ApplicationUser.issuer == records["issuer"], ApplicationUser.subject == subject,
        )) == 1
