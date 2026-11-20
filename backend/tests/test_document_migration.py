"""Populated previous-head upgrade and new-schema-only downgrade, disposable only."""

import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

from app.models import ApplicationUser, Base, Document, DocumentJob, WorkspaceMembership
from app.seed_demo import initialize_demo
from app.workspace import DEMO_WORKSPACE_ID
from scripts.check_schema import migration_config, require_test_marker, verify_revision
from tests.test_document_schema import NOW

pytestmark = pytest.mark.postgres
PREVIOUS = "0002_auth_workspaces"
REVISION = "0003_documents"
NEW_TABLES = {"documents", "document_jobs"}


def test_populated_previous_head_and_document_only_downgrade_preserve_all_old_rows(postgres_engine):
    config = migration_config()
    old_tables = [table for table in Base.metadata.sorted_tables if table.name not in NEW_TABLES]
    user_id = uuid4()

    def snapshot(connection):
        return {table.name: connection.execute(select(table).order_by(table.c.id)).all() for table in old_tables}

    def guard():
        with postgres_engine.connect() as connection:
            require_test_marker(connection, os.environ)

    with postgres_engine.connect() as connection:
        require_test_marker(connection, os.environ)
        for table in Base.metadata.sorted_tables:
            assert connection.execute(select(table).limit(1)).first() is None
    try:
        guard()
        command.downgrade(config, PREVIOUS)
        with Session(postgres_engine) as session:
            require_test_marker(session.connection(), os.environ)
            initialize_demo(session)
            session.add(ApplicationUser(id=user_id, issuer="https://fictional.invalid", subject="pre-document-uploader"))
            session.flush()
            session.add(WorkspaceMembership(workspace_id=DEMO_WORKSPACE_ID, application_user_id=user_id, role="administrator"))
            session.commit()
        with postgres_engine.connect() as connection:
            before = snapshot(connection)
            assert all(before[table.name] for table in old_tables)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with postgres_engine.connect() as connection:
            assert verify_revision(connection) == REVISION
            assert snapshot(connection) == before
            for model in (Document, DocumentJob):
                assert connection.scalar(select(func.count()).select_from(model)) == 0
        with Session(postgres_engine) as session:
            require_test_marker(session.connection(), os.environ)
            document = Document(
                workspace_id=DEMO_WORKSPACE_ID, uploader_id=user_id, upload_attempt_key=uuid4(),
                storage_key=f"fictional-migration/{uuid4()}", original_filename="fictional.pdf",
                byte_size=2048, sha256="a" * 64, state="queued", uploaded_at=NOW,
            )
            session.add(document)
            session.flush()
            document_id = document.id
            session.add(DocumentJob(
                document=document, workspace_id=DEMO_WORKSPACE_ID,
                dispatch_state="pending", next_dispatch_at=NOW, next_attempt_at=NOW,
            ))
            session.commit()
        with Session(postgres_engine) as session:
            require_test_marker(session.connection(), os.environ)
            job = session.get(DocumentJob, document_id)
            assert job.document.id == document_id and job.document.uploader.id == user_id
            assert job.workspace_id == job.document.workspace_id == DEMO_WORKSPACE_ID
        guard()
        command.downgrade(config, PREVIOUS)
        with postgres_engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) == {table.name for table in old_tables} | {"alembic_version"}
            assert snapshot(connection) == before
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS
        command.upgrade(config, "head")
        with postgres_engine.connect() as connection:
            assert verify_revision(connection) == REVISION
            assert snapshot(connection) == before
            for model in (Document, DocumentJob):
                assert connection.scalar(select(func.count()).select_from(model)) == 0
    finally:
        # Restore the head even on failure, then remove only this test's known rows.
        guard()
        command.upgrade(config, "head")
        with postgres_engine.begin() as connection:
            require_test_marker(connection, os.environ)
            for table in reversed(Base.metadata.sorted_tables):
                if table.name == "application_users":
                    condition = table.c.id == user_id
                elif table.name == "workspaces":
                    condition = table.c.id == DEMO_WORKSPACE_ID
                else:
                    condition = table.c.workspace_id == DEMO_WORKSPACE_ID
                connection.execute(delete(table).where(condition))
