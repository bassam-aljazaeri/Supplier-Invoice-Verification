"""Separate prefork worker; fail closed if Linux parser containment is unavailable."""

from app.celery_app import app
from app.document_validation import check_containment


def main():
    check_containment()
    app.worker_main(["worker", "--pool=prefork", "--concurrency=1", "--queues=documents", "--loglevel=WARNING", "--without-gossip", "--without-mingle"])


if __name__ == "__main__":
    main()
