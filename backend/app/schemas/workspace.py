import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import MembershipRole
from app.schemas.common import CreateModel, Identifier, Name, RecordList


class WorkspaceCreate(CreateModel):
    slug: Identifier
    name: Name

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value):
        if value == "local-demo" or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is None:
            raise ValueError("Choose an available workspace slug.")
        return value


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    created_at: datetime


class AccessibleWorkspace(WorkspaceRead):
    role: MembershipRole


WorkspaceList = RecordList[AccessibleWorkspace]
