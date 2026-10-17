"""Operator command behavior, synthetic settings, and guarded PostgreSQL writes."""

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import bootstrap_membership as cli
from app.models import ApplicationUser, Workspace, WorkspaceMembership
from app.seed_demo import initialize_demo
from app.seed_workspace import initialize_workspace
from app.services.identity import IdentityError
from app.services.memberships import MembershipConflict, MembershipNotFound

ISSUER = "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE"
VALUES = {"issuer": ISSUER, "subject": "synthetic-operator-subject", "workspace_slug": "local-demo", "role": "administrator"}


@pytest.fixture
def synthetic_cognito(monkeypatch):
    monkeypatch.setenv("COGNITO_REGION", "eu-west-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-west-1_EXAMPLE")


def access_snapshot(session):
    return {model.__tablename__: session.execute(select(model.__table__).order_by(model.id)).all() for model in (ApplicationUser, WorkspaceMembership)}


@pytest.mark.postgres
@pytest.mark.parametrize("role", ["administrator", "accountant", "approver"])
def test_bootstrap_creates_identity_and_repeats_without_changes(schema_session, role):
    workspace = initialize_workspace(schema_session)
    before_workspace = (workspace.id, workspace.slug, workspace.name, workspace.created_at)
    first = cli.bootstrap_membership(schema_session, **(VALUES | {"role": role}))
    assert first.workspace_id == workspace.id and first.role == role
    before = access_snapshot(schema_session)
    repeated = cli.bootstrap_membership(schema_session, **(VALUES | {"role": role}))
    assert repeated.id == first.id and access_snapshot(schema_session) == before
    user = schema_session.get(ApplicationUser, first.application_user_id)
    assert (user.issuer, user.subject, user.is_active) == (ISSUER, VALUES["subject"], True)
    assert (workspace.id, workspace.slug, workspace.name, workspace.created_at) == before_workspace


@pytest.mark.postgres
def test_missing_workspace_never_creates_workspace_or_identity(schema_session):
    with pytest.raises(MembershipNotFound):
        cli.bootstrap_membership(schema_session, **VALUES)
    for model in (ApplicationUser, WorkspaceMembership, Workspace):
        assert schema_session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.postgres
def test_conflicting_role_rolls_back_without_overwriting(schema_session):
    initialize_workspace(schema_session)
    cli.bootstrap_membership(schema_session, **VALUES)
    before = access_snapshot(schema_session)
    with pytest.raises(MembershipConflict, match="different membership role"):
        cli.bootstrap_membership(schema_session, **(VALUES | {"role": "accountant"}))
    assert access_snapshot(schema_session) == before


@pytest.mark.postgres
def test_noncommitting_helper_and_late_commit_failure_leave_no_partial_grant(schema_session):
    initialize_workspace(schema_session)
    commits = []
    event.listen(schema_session, "before_commit", lambda session: commits.append(True))
    cli.ensure_bootstrap_membership(schema_session, **VALUES)
    assert commits == []
    schema_session.rollback()
    assert access_snapshot(schema_session) == {"application_users": [], "workspace_memberships": []}

    def fail_commit(session):
        raise OperationalError("synthetic-private-statement", None, RuntimeError("synthetic-private-failure"))

    event.listen(schema_session, "before_commit", fail_commit)
    try:
        with pytest.raises(OperationalError):
            cli.bootstrap_membership(schema_session, **VALUES)
    finally:
        event.remove(schema_session, "before_commit", fail_commit)
    assert access_snapshot(schema_session) == {"application_users": [], "workspace_memberships": []}
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 1
    assert cli.bootstrap_membership(schema_session, **VALUES).role == "administrator"


@pytest.mark.postgres
def test_bootstrap_refuses_to_reactivate_an_existing_identity(schema_session):
    initialize_workspace(schema_session)
    membership = cli.bootstrap_membership(schema_session, **VALUES)
    user = schema_session.get(ApplicationUser, membership.application_user_id)
    user.is_active = False
    schema_session.commit()
    before = access_snapshot(schema_session)
    with pytest.raises(IdentityError, match="inactive"):
        cli.bootstrap_membership(schema_session, **VALUES)
    assert access_snapshot(schema_session) == before


@pytest.mark.postgres
def test_bootstrap_and_repeated_seeding_preserve_all_business_and_access_rows(schema_session):
    from app.models import Base

    initialize_demo(schema_session)
    business_tables = [table for table in Base.metadata.sorted_tables if table.name not in {"application_users", "workspace_memberships"}]

    def business_snapshot():
        return {table.name: schema_session.execute(select(table).order_by(table.c.id)).all() for table in business_tables}

    before = business_snapshot()
    membership = cli.bootstrap_membership(schema_session, **VALUES)
    access = access_snapshot(schema_session)
    initialize_demo(schema_session)
    initialize_demo(schema_session)
    assert business_snapshot() == before and access_snapshot(schema_session) == access
    assert schema_session.get(WorkspaceMembership, membership.id) is not None


@pytest.mark.postgres
def test_main_commits_and_sanitizes_failures(schema_session, synthetic_cognito, monkeypatch, capsys):
    initialize_workspace(schema_session)
    connection = schema_session.connection()
    monkeypatch.setattr(cli, "SessionLocal", lambda: Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False))
    args = ["--subject", VALUES["subject"], "--workspace-slug", "local-demo", "--role", "administrator"]
    assert cli.main(args) == cli.main(args) == 0
    assert schema_session.scalar(select(func.count()).select_from(ApplicationUser)) == 1
    assert cli.main(args[:-1] + ["approver"]) == 1
    output = capsys.readouterr()
    assert VALUES["subject"] not in output.out + output.err and ISSUER not in output.out + output.err
    assert "application_user_id=" in output.out and "nothing was replaced" in output.err


def test_missing_configuration_fails_before_database_access(monkeypatch, capsys):
    monkeypatch.delenv("COGNITO_REGION", raising=False)
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    monkeypatch.setattr(cli, "SessionLocal", lambda: pytest.fail("Database must not open with invalid configuration."))
    assert cli.main(["--subject", "synthetic", "--workspace-slug", "local-demo", "--role", "administrator"]) == 1
    assert "COGNITO_REGION" in capsys.readouterr().err


@pytest.mark.parametrize("args", [[], ["--subject", "synthetic-private-token"], ["--subject", "synthetic-private-token", "--workspace-slug", "local-demo", "--role", "synthetic-private-role"], ["--subject", "synthetic", "--workspace-slug", "local-demo", "--role", "administrator", "--issuer", "synthetic-private-issuer"]])
def test_argument_errors_do_not_echo_supplied_values(args, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "synthetic-private" not in output.out + output.err


def test_unexpected_failure_is_sanitized(synthetic_cognito, monkeypatch, capsys):
    def fail_session():
        raise RuntimeError("synthetic-private-credentials-and-token")

    monkeypatch.setattr(cli, "SessionLocal", fail_session)
    assert cli.main(["--subject", "synthetic", "--workspace-slug", "local-demo", "--role", "administrator"]) == 1
    output = capsys.readouterr()
    assert "No partial grant was saved" in output.err and "synthetic-private" not in output.err


@pytest.mark.postgres
def test_actual_module_command_persists_repeat_and_conflict(postgres_engine, committed_memberships, synthetic_cognito):
    records = committed_memberships
    subject = "cli-" + uuid4().hex
    records["subjects"].append(subject)
    args = [sys.executable, "-m", "app.bootstrap_membership", "--subject", subject, "--workspace-slug", records["slug"], "--role", "administrator"]
    first = subprocess.run(args, capture_output=True, text=True, timeout=15, env=os.environ.copy())
    assert first.returncode == 0, first.stderr
    with Session(postgres_engine) as session:
        before = access_snapshot(session)
    second = subprocess.run(args, capture_output=True, text=True, timeout=15, env=os.environ.copy())
    conflict = subprocess.run(args[:-1] + ["accountant"], capture_output=True, text=True, timeout=15, env=os.environ.copy())
    assert second.returncode == 0 and second.stdout == first.stdout and conflict.returncode == 1
    with Session(postgres_engine) as session:
        assert access_snapshot(session) == before
    assert subject not in first.stdout + second.stdout + conflict.stderr
    assert "nothing was replaced" in conflict.stderr
