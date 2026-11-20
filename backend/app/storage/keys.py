"""Opaque server keys shared by private storage adapters."""

import re
from uuid import UUID, uuid4

from app.storage import StorageIntegrity

MAX_FILE_SIZE = 5000000
CHUNK_SIZE = 65536
STORAGE_TIMEOUT = 15
KEY_PATTERN = re.compile(r"d-[0-9a-f]{32}-[0-9a-f]{32}-[0-9a-f]{32}\Z")


def new_key(workspace_id: UUID, document_id: UUID) -> str:
    return f"d-{workspace_id.hex}-{document_id.hex}-{uuid4().hex}"


def check_key(key):
    if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
        raise StorageIntegrity()
