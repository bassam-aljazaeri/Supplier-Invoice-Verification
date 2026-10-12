from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import seed_workspace
from app.models import Base, Workspace
from app.seed_workspace import WorkspaceConflict, ensure_demo_workspace, initialize_workspace
from app.workspace import DEMO_WORKSPACE_ID, DEMO_WORKSPACE_NAME, DEMO_WORKSPACE_SLUG

pytestmark = pytest.mark.postgres


def test_workspace_initialization_twice_only_creates_expected_workspace(schema_session):
    first = initialize_workspace(schema_session)
    snapshot = (first.id, first.slug, first.name, first.created_at)
    second = initialize_workspace(schema_session)
    assert (second.id, second.slug, second.name, second.created_at) == snapshot
    assert snapshot[:3] == (DEMO_WORKSPACE_ID, DEMO_WORKSPACE_SLUG, DEMO_WORKSPACE_NAME)
    for table in Base.metadata.tables.values():
        expected = 1 if table.name == "workspaces" else 0
        assert schema_session.scalar(select(func.count()).select_from(table)) == expected


def test_reusable_workspace_helper_does_not_commit(schema_session):
    ensure_demo_workspace(schema_session)
    schema_session.rollback()
    assert schema_session.get(Workspace, DEMO_WORKSPACE_ID) is None


@pytest.mark.parametrize("conflict", ["id", "slug", "name", "split"])
def test_conflicting_workspace_data_is_not_overwritten(schema_session, conflict):
    rows = {
        "id": [Workspace(id=DEMO_WORKSPACE_ID, slug="other", name="Synthetic existing")],
        "slug": [Workspace(id=uuid4(), slug=DEMO_WORKSPACE_SLUG, name=DEMO_WORKSPACE_NAME)],
        "name": [Workspace(id=DEMO_WORKSPACE_ID, slug=DEMO_WORKSPACE_SLUG, name="Synthetic conflicting name")],
        "split": [Workspace(id=DEMO_WORKSPACE_ID, slug="other", name="Synthetic existing"), Workspace(id=uuid4(), slug=DEMO_WORKSPACE_SLUG, name=DEMO_WORKSPACE_NAME)],
    }[conflict]
    schema_session.add_all(rows)
    schema_session.commit()
    statement = select(Workspace.id, Workspace.slug, Workspace.name).order_by(Workspace.id)
    before = schema_session.execute(statement).all()
    with pytest.raises(WorkspaceConflict, match="nothing was overwritten"):
        initialize_workspace(schema_session)
    assert schema_session.execute(statement).all() == before


def test_cli_initialization_twice_and_conflict_exit(schema_session, monkeypatch, capsys):
    connection = schema_session.connection()
    monkeypatch.setattr(seed_workspace, "SessionLocal", lambda: Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False))
    assert seed_workspace.main() == 0
    assert seed_workspace.main() == 0
    assert schema_session.scalar(select(func.count()).select_from(Workspace)) == 1
    workspace = schema_session.get(Workspace, DEMO_WORKSPACE_ID)
    workspace.name = "Synthetic private conflict value"
    schema_session.commit()
    assert seed_workspace.main() == 1
    output = capsys.readouterr()
    assert "nothing was overwritten" in output.err
    assert "Synthetic private conflict value" not in output.err
