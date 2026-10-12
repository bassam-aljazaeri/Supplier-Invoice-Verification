import os

import pytest
from alembic import command
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db import create_database_engine, get_session
from scripts.check_schema import (
    TestTargetError, approved_test_url, migration_config, require_test_marker, verify_revision,
)


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
def api_client(schema_session):
    """Each real API request gets a session whose commits stay in the test transaction."""
    from app.main import app

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
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
