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

``auth`` reports what sign-up depends on: the Google OAuth client IDs accepted
as ID-token audiences (public identifiers — the app ships them) and which email
backend delivers verification codes. ``console`` there means codes are printed
to the server log and never reach an inbox.
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


_EMAIL_BACKEND_LABELS = {
    "anymail.backends.resend.EmailBackend": "resend",
    "django.core.mail.backends.smtp.EmailBackend": "smtp",
    "django.core.mail.backends.console.EmailBackend": "console (codes are not emailed)",
}


def _auth() -> dict:
    from lipaidox.auth.googleOuth.googleOuth import _google_oauth_audiences

    return {
        "googleClientIds": _google_oauth_audiences(),
        "emailBackend": _EMAIL_BACKEND_LABELS.get(settings.EMAIL_BACKEND, "custom"),
        "emailFromConfigured": bool(settings.DEFAULT_FROM_EMAIL),
        # Domain only, never the mailbox. `resend.dev` is Resend's testing sender,
        # which delivers solely to the Resend account owner's own address.
        "emailFromDomain": (settings.DEFAULT_FROM_EMAIL or "").rpartition("@")[2].strip(" >") or None,
        # Host name only (e.g. smtp.gmail.com) — never the user or password.
        "emailSmtpHost": settings.EMAIL_HOST or None,
        "emailSmtpLoginConfigured": bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD),
        "emailVerificationInlineOtp": bool(settings.EMAIL_VERIFICATION_INLINE_OTP),
        "firebase": _firebase(),
    }


def _firebase() -> dict:
    """Whether Firebase sign-in can verify tokens — project id and credential source, never the key."""
    from lipaidox.auth.googleOuth.googleOuth import FirebaseAuthService

    svc = FirebaseAuthService()
    try:
        svc.ensure_initialized()
    except Exception as exc:  # never let health checks raise
        return {"projectId": settings.FIREBASE_PROJECT_ID or None, "adminReady": False, "error": type(exc).__name__}
    return {
        "projectId": settings.FIREBASE_PROJECT_ID or None,
        "adminReady": svc.initialized,
        # env | file | path | adc — which credential source Admin started with.
        "credentials": svc.credential_source,
        "checkRevoked": bool(settings.FIREBASE_CHECK_REVOKED),
    }


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
    body = {
        "status": "ok" if all_ok else ("degraded" if db_ok else "down"),
        "checks": checks,
        "auth": _auth(),
    }
    return JsonResponse(body, status=200 if db_ok else 503)
