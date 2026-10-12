"""Explicitly initialize only the fixed workspace: python -m app.seed_workspace."""

import sys

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Workspace
from app.workspace import (
    DEMO_WORKSPACE_ID, DEMO_WORKSPACE_NAME, DEMO_WORKSPACE_SLUG, is_demo_workspace,
)


class WorkspaceConflict(RuntimeError):
    pass


def ensure_demo_workspace(session: Session) -> Workspace:
    """Reusable by a later seeder; the caller owns commit/rollback."""
    # DO NOTHING also handles simultaneous initializers without overwriting data.
    session.execute(insert(Workspace).values(
        id=DEMO_WORKSPACE_ID, slug=DEMO_WORKSPACE_SLUG, name=DEMO_WORKSPACE_NAME,
    ).on_conflict_do_nothing())
    matches = list(session.scalars(select(Workspace).where(or_(
        Workspace.id == DEMO_WORKSPACE_ID, Workspace.slug == DEMO_WORKSPACE_SLUG,
    )).execution_options(populate_existing=True)))
    if len(matches) != 1 or not is_demo_workspace(matches[0]):
        raise WorkspaceConflict(
            "Demo workspace ID/slug/name conflicts with existing data; nothing was overwritten."
        )
    return matches[0]


def initialize_workspace(session: Session) -> Workspace:
    try:
        workspace = ensure_demo_workspace(session)
        session.commit()
        return workspace
    except BaseException:
        session.rollback()
        raise


def main() -> int:
    try:
        with SessionLocal() as session:
            initialize_workspace(session)
        print("Local demo workspace initialized; no business records were seeded.")
        return 0
    except WorkspaceConflict as error:
        print(str(error), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Workspace initialization failed; check PostgreSQL and apply migrations first.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
