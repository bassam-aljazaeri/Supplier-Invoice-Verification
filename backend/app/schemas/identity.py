from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.membership import OwnMembership


class ApplicationUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    issuer: str
    subject: str
    created_at: datetime
    updated_at: datetime


class MeRead(BaseModel):
    user: ApplicationUserRead
    memberships: list[OwnMembership]
