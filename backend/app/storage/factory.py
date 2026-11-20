"""Trusted process configuration; local mode never initializes an AWS SDK client."""

import os

from app.storage import StorageIntegrity


def configured_storage(settings=None):
    settings = os.environ if settings is None else settings
    backend = settings.get("DOCUMENT_STORAGE_BACKEND", "local")
    if backend == "local":
        from app.storage.local import LocalDocumentStorage
        return LocalDocumentStorage(settings.get("DOCUMENT_STORAGE_ROOT", "/var/lib/supplier-invoice-verification/documents"))
    if backend == "s3":
        from app.storage.s3 import S3DocumentStorage
        return S3DocumentStorage(
            settings.get("DOCUMENT_S3_BUCKET", ""), settings.get("DOCUMENT_S3_REGION", ""),
            settings.get("DOCUMENT_S3_PREFIX", ""),
        )
    raise StorageIntegrity()
