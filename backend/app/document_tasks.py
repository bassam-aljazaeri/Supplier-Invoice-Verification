"""Delivery is at least once. Atomic claims and lease fencing make repeats safe."""

from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from app.celery_app import app
from app.document_runtime import DocumentRuntime
from app.document_validation import validate
from app.services.document_jobs import Jobs
from app.storage import StorageError, StorageIntegrity


def process_document(document_id, *, jobs=None, storage=None, after_claim=None):
    try:
        identity = UUID(str(document_id))
    except (ValueError, TypeError):
        return
    jobs = jobs or Jobs()
    try:
        attempt = jobs.claim(identity)
        if attempt is None:
            return
        try:
            if after_claim is not None:
                after_claim(identity)
            result = validate(storage or DocumentRuntime().get_storage(), attempt)
        except StorageIntegrity:
            result = {"state": "failed", "code": "storage_integrity"}
        except StorageError:
            result = {"state": "temporary", "code": "storage_unavailable"}
        except SoftTimeLimitExceeded:
            result = {"state": "temporary", "code": "processing_interrupted"}
        except Exception:
            result = {"state": "temporary", "code": "processing_error"}
        jobs.complete(attempt, **result)
    except (SQLAlchemyError, SoftTimeLimitExceeded):
        # Leave claim/durable scheduling to lease reconciliation. Never log SQL/input.
        return


@app.task(name="documents.validate")
def validate_document(document_id):
    process_document(document_id)
