"""Upgrade populated 0001 only on the guarded disposable database, then clean up."""

import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

from app.models import ApplicationUser, Base, Supplier, Workspace, WorkspaceMembership
from app.seed_demo import initialize_demo
from app.workspace import DEMO_WORKSPACE_ID
from scripts.check_schema import migration_config, require_test_marker

pytestmark = pytest.mark.postgres


def test_additive_upgrade_preserves_populated_initial_records(postgres_engine):
    config = migration_config()
    tables = [table for table in Base.metadata.sorted_tables if table.name not in {"application_users", "workspace_memberships"}]
    workspace_ids = [DEMO_WORKSPACE_ID, uuid4()]

    def snapshot(connection):
        return {table.name: connection.execute(select(table).order_by(table.c.id)).all() for table in tables}

    with postgres_engine.connect() as connection:
        require_test_marker(connection, os.environ)
        for table in Base.metadata.sorted_tables:
            assert connection.execute(select(table).limit(1)).first() is None
    try:
        command.downgrade(config, "0001_manual_records")
        with Session(postgres_engine) as session:
            require_test_marker(session.connection(), os.environ)
            initialize_demo(session)
            session.add(Workspace(id=workspace_ids[1], slug="pre-auth-existing", name="Synthetic existing company"))
            session.flush()
            session.add(Supplier(workspace_id=workspace_ids[1], supplier_code="PRE-AUTH", name="Synthetic existing supplier"))
            session.commit()
        with postgres_engine.connect() as connection:
            before = snapshot(connection)
            assert len(before["workspaces"]) == 2 and len(before["invoices"]) == 1
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001_manual_records"
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with postgres_engine.connect() as connection:
            assert snapshot(connection) == before
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_auth_workspaces"
            for model in (ApplicationUser, WorkspaceMembership):
                assert connection.scalar(select(func.count()).select_from(model)) == 0
    finally:
        # Targeted deletion of this test's known workspace IDs only, never reset.
        with postgres_engine.begin() as connection:
            require_test_marker(connection, os.environ)
            if "workspace_memberships" in inspect(connection).get_table_names():
                connection.execute(delete(WorkspaceMembership).where(WorkspaceMembership.workspace_id.in_(workspace_ids)))
            for table in reversed(tables):
                condition = table.c.id.in_(workspace_ids) if table.name == "workspaces" else table.c.workspace_id.in_(workspace_ids)
                connection.execute(delete(table).where(condition))
        command.upgrade(config, "head")
