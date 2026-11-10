"""Private storage boundary. No AWS client or network fallback in local mode."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol
from uuid import UUID


class StorageError(Exception):
    pass


class StorageMissing(StorageError):
    pass


class StorageUnavailable(StorageError):
    pass


class StorageIntegrity(StorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class StorageCandidate:
    key: str
    partial: bool
    modified: float
    device: int
    inode: int


@dataclass(frozen=True)
class DownloadGrant:
    url: str
    expires_at: datetime


class DocumentStorage(Protocol):
    def put_new(self, key: str, file: BinaryIO, size: int, sha256: str) -> None: ...
    def open_bounded(self, key: str, max_bytes: int) -> AbstractContextManager: ...
    def stat(self, key: str) -> StoredObject: ...
    def delete(self, key: str) -> None: ...
    def cleanup_candidates(self) -> list[StorageCandidate]: ...
    def delete_candidate(self, candidate: StorageCandidate, older_than: float) -> bool: ...
    def download_grant(self, document_id: UUID, workspace_id: UUID, caller_id: UUID, expires_in: int) -> DownloadGrant: ...
    def verify_ticket(self, ticket: str, document_id: UUID, workspace_id: UUID, caller_id: UUID) -> bool: ...
