"""Public projections exclude storage identifiers, hashes, keys, and lease owners."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.models import DocumentErrorCode, DocumentState, DocumentType
from app.schemas.common import Pagination, ReadRecord, RecordList


class DocumentRead(ReadRecord):
    uploader_id: UUID
    original_filename: str
    byte_size: int
    detected_type: DocumentType | None
    state: DocumentState
    error_code: DocumentErrorCode | None
    can_retry: bool = False
    updated_at: datetime
    uploaded_at: datetime | None
    finished_at: datetime | None

    @field_serializer("updated_at", "uploaded_at", "finished_at")
    def timestamps(self, value):
        return None if value is None else value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class DocumentQuery(Pagination):
    state: DocumentState | None = None
    upload_attempt_key: UUID | None = None


DocumentList = RecordList[DocumentRead]


class DocumentDownload(BaseModel):
    document_id: UUID
    workspace_id: UUID
    delivery: Literal["local_authenticated", "s3_presigned"]
    url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def timestamp(self, value):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
