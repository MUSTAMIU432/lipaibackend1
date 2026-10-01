"""
Enqueueing background work from request code.

``enqueue_on_commit(task, *args)`` queues a Celery task once the surrounding
transaction commits (so the worker never looks for a row that isn't visible
yet). If the broker can't be reached, the task runs inline instead — slower
for that one request, but the work still happens, which is how these calls
behaved before Celery was wired in.

With no broker configured at all (Render today), eager tasks would run inside
the request that queued them — publishing a video then waited for ffmpeg
before answering, long enough for the app to give up and report a failure
for a post that was in fact saved. ``BACKGROUND_EAGER_TASKS`` (on by default
whenever tasks are eager) runs them on a background thread instead, so the
response returns at once and the work still happens in this process.

Pass ids and plain values as arguments, never model instances or secrets:
arguments are JSON-serialized into Redis and show up in worker logs.
"""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db import connections, transaction

logger = logging.getLogger(__name__)


def _run_detached(task, args, kwargs) -> None:
    try:
        task.apply(args=args, kwargs=kwargs)
    except Exception:  # pragma: no cover - apply() already captures task errors
        logger.exception("background task %s failed", task.name)
    finally:
        # This thread opened its own DB connections; don't leak them.
        connections.close_all()


def enqueue(task, *args, **kwargs) -> None:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) and getattr(settings, "BACKGROUND_EAGER_TASKS", False):
        threading.Thread(
            target=_run_detached, args=(task, args, kwargs), name=f"task:{task.name}", daemon=True
        ).start()
        return
    try:
        task.apply_async(args=args, kwargs=kwargs)
    except Exception:
        logger.warning("celery: enqueue of %s failed, running inline", task.name, exc_info=True)
        task.apply(args=args, kwargs=kwargs)


def enqueue_on_commit(task, *args, **kwargs) -> None:
    transaction.on_commit(lambda: enqueue(task, *args, **kwargs))
