"""Bounded publisher child: only an identifier and broker configuration."""

import sys
from uuid import UUID


def main():
    try:
        from app.celery_app import app
        identity = str(UUID(sys.argv[1]))
        app.send_task("documents.validate", kwargs={"document_id": identity}, retry=False, ignore_result=True)
        return 0
    except Exception:
        return 1  # No exception details, connection credentials or payload logging.


if __name__ == "__main__":
    sys.exit(main())
