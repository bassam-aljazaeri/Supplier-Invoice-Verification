import os

import pytest
from alembic import command
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db import create_database_engine, get_session
from scripts.check_schema import (
    TestTargetError, approved_test_url, migration_config, require_test_marker, verify_revision,
)
from tests.auth_helpers import BUSINESS_SUBJECT, SETTINGS, SigningKeys


@pytest.fixture(scope="session")
def signing_keys():
    return SigningKeys()


@pytest.fixture
def auth_verifier(signing_keys):
    return signing_keys.verifier()


@pytest.fixture
def grant_demo_access(schema_session):
    def grant():
        from app.services.identity import ensure_application_user
        from app.services.memberships import ensure_membership
        from app.workspace import DEMO_WORKSPACE_ID

        user = ensure_application_user(schema_session, SETTINGS.issuer, BUSINESS_SUBJECT)
        ensure_membership(schema_session, DEMO_WORKSPACE_ID, user.id, "administrator")
        schema_session.commit()
        return user
    return grant


@pytest.fixture(scope="session")
def postgres_engine():
    if os.environ.get("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("PostgreSQL integration tests require opt-in through the disposable checker (RUN_POSTGRES_TESTS=1).")
    try:
        url = approved_test_url(os.environ)
    except TestTargetError as error:
        pytest.fail(str(error), pytrace=False)
    engine = create_database_engine(url)
    try:
        with engine.connect() as connection:
            require_test_marker(connection, os.environ)
        # The guard runs before any schema writes. No create_all or development fallback.
        command.upgrade(migration_config(), "head")
        with engine.connect() as connection:
            verify_revision(connection)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def schema_session(postgres_engine):
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def api_client(schema_session, auth_verifier, signing_keys):
    """Each real API request gets a session whose commits stay in the test transaction."""
    from app.main import create_app
    from app.workspace import DEMO_WORKSPACE_ID

    app = create_app(verifier=auth_verifier)

    connection = schema_session.connection()

    def test_session():
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.headers.update({"Authorization": "Bearer " + signing_keys.token(), "X-Workspace-ID": str(DEMO_WORKSPACE_ID)})
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest.fixture
def committed_memberships(postgres_engine):
    """Guarded committed rows for separate-connection races and real CLI checks."""
    from uuid import uuid4

    from sqlalchemy import delete

    from app.models import ApplicationUser, Workspace, WorkspaceMembership
    from app.services.identity import ensure_application_user
    from app.services.memberships import ensure_membership

    token = uuid4().hex
    records = {
        "workspace_id": uuid4(), "slug": "membership-check-" + token,
        "issuer": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EXAMPLE",
        "subjects": [f"{token}-{index}" for index in range(3)], "user_ids": [],
    }
    try:
        with Session(postgres_engine, expire_on_commit=False) as session:
            require_test_marker(session.connection(), os.environ)
            session.add(Workspace(id=records["workspace_id"], slug=records["slug"], name="Synthetic membership check"))
            session.flush()
            for index, subject in enumerate(records["subjects"]):
                user = ensure_application_user(session, records["issuer"], subject)
                records["user_ids"].append(user.id)
                if index < 2:
                    ensure_membership(session, records["workspace_id"], user.id, "administrator")
            session.commit()
        yield records
    finally:
        with postgres_engine.begin() as connection:
            require_test_marker(connection, os.environ)
            connection.execute(delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id == records["workspace_id"]))
            connection.execute(delete(Workspace).where(Workspace.id == records["workspace_id"]))
            connection.execute(delete(ApplicationUser).where(
                ApplicationUser.issuer == records["issuer"], ApplicationUser.subject.in_(records["subjects"]),
            ))
