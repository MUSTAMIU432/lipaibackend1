"""
Enqueueing background work from request code.

``enqueue_on_commit(task, *args)`` queues a Celery task once the surrounding
transaction commits (so the worker never looks for a row that isn't visible
yet). If the broker can't be reached, the task runs inline instead — slower
for that one request, but the work still happens, which is how these calls
behaved before Celery was wired in. With no broker configured at all,
``CELERY_TASK_ALWAYS_EAGER`` makes ``apply_async`` run inline anyway.

Pass ids and plain values as arguments, never model instances or secrets:
arguments are JSON-serialized into Redis and show up in worker logs.
"""
from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def enqueue(task, *args, **kwargs) -> None:
    try:
        task.apply_async(args=args, kwargs=kwargs)
    except Exception:
        logger.warning("celery: enqueue of %s failed, running inline", task.name, exc_info=True)
        task.apply(args=args, kwargs=kwargs)


def enqueue_on_commit(task, *args, **kwargs) -> None:
    transaction.on_commit(lambda: enqueue(task, *args, **kwargs))
