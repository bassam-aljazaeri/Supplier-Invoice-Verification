from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import MembershipRole
from app.schemas.common import CreateModel, RecordList
from app.schemas.workspace import WorkspaceRead


class MembershipRoleChange(CreateModel):
    role: MembershipRole


class MembershipCreate(MembershipRoleChange):
    application_user_id: UUID


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    application_user_id: UUID
    role: MembershipRole
    created_at: datetime
    updated_at: datetime


class OwnMembership(MembershipRead):
    workspace: WorkspaceRead


class WorkspaceCreated(BaseModel):
    workspace: WorkspaceRead
    membership: MembershipRead


MembershipList = RecordList[MembershipRead]
