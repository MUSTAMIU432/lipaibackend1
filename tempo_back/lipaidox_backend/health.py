"""
GET /health/ — infrastructure status: PostgreSQL, cache (Redis), Celery broker,
and (with ``?workers=1``, DEBUG only) a live worker round-trip. The worker
check is DEBUG-only because it queues a task and waits up to 5 s — a public
endpoint mustn't let anyone flood the queue; in production use
``celery -A lipaidox_backend inspect ping``.

Returns 503 only when PostgreSQL is down. A Redis or worker outage is reported
as ``degraded`` with 200, because the app keeps serving without them (cache
misses fall through to Postgres, tasks run inline). Never includes URLs,
hosts or credentials — just ``ok`` / ``not configured`` / an exception class.
"""
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from lipaidox.cache import cache_health


def _database() -> str:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return "ok"
    except Exception as exc:
        return type(exc).__name__


def _cache() -> str:
    err = cache_health()
    if err:
        return err
    return "ok" if settings.REDIS_URL else "ok (in-process memory, REDIS_URL not set)"


def _broker() -> str:
    if not settings.CELERY_BROKER_URL:
        return "not configured (tasks run inline)"
    from lipaidox_backend.celery import app

    try:
        with app.connection_for_write() as conn:
            conn.ensure_connection(max_retries=1, timeout=2)
        return "ok"
    except Exception as exc:
        return type(exc).__name__


def _workers() -> str:
    from lipaidox.tasks import ping

    try:
        return "ok" if ping.apply_async().get(timeout=5) == "pong" else "no reply"
    except Exception as exc:
        return type(exc).__name__


@require_GET
def health_view(request):
    checks = {"database": _database(), "cache": _cache(), "broker": _broker()}
    if (
        settings.DEBUG
        and request.GET.get("workers") == "1"
        and settings.CELERY_BROKER_URL
        and settings.CELERY_RESULT_BACKEND
    ):
        checks["workers"] = _workers()

    db_ok = checks["database"] == "ok"
    all_ok = db_ok and all(v.startswith(("ok", "not configured")) for v in checks.values())
    body = {"status": "ok" if all_ok else ("degraded" if db_ok else "down"), "checks": checks}
    return JsonResponse(body, status=200 if db_ok else 503)
