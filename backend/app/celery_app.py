"""Redis transports identifiers; PostgreSQL alone owns results and retry timing."""

import os

from celery import Celery

app = Celery("supplier_invoice_verification", broker=f"redis://{os.getenv('REDIS_HOST', 'redis')}:{int(os.getenv('REDIS_PORT', '6379'))}/1", include=["app.document_tasks"])
app.conf.update(
    accept_content=["json"], task_serializer="json", result_serializer="json",
    result_backend=None, task_ignore_result=True, task_store_errors_even_if_ignored=False,
    task_default_queue="documents", task_acks_late=True,
    task_acks_on_failure_or_timeout=True, task_reject_on_worker_lost=False,
    worker_cancel_long_running_tasks_on_connection_loss=True, worker_prefetch_multiplier=1,
    worker_concurrency=1, worker_enable_remote_control=False,
    task_soft_time_limit=45, task_time_limit=60, visibility_timeout=180,
    broker_transport_options={"visibility_timeout": 180, "global_keyprefix": "siv-documents:", "socket_connect_timeout": 2, "socket_timeout": 3},
    broker_connection_timeout=2, broker_connection_retry_on_startup=True,
    task_publish_retry=False, broker_pool_limit=1,
)
