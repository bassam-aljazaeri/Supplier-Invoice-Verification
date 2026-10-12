"""Fixed local demo context, not authentication or a company security boundary."""

from uuid import UUID

from app.models import Workspace

DEMO_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
DEMO_WORKSPACE_SLUG = "local-demo"
DEMO_WORKSPACE_NAME = "Local demo workspace"


def is_demo_workspace(workspace: Workspace) -> bool:
    return (
        workspace.id == DEMO_WORKSPACE_ID
        and workspace.slug == DEMO_WORKSPACE_SLUG
        and workspace.name == DEMO_WORKSPACE_NAME
    )
