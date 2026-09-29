"""Scheduled credit jobs (see CELERY_BEAT_SCHEDULE in settings)."""
from celery import shared_task


@shared_task(name="lipaidox.credits.bill_live_sessions")
def bill_live_sessions_task() -> dict:
    """Beat job, every minute — same pass as `manage.py bill_live_sessions`."""
    from lipaidox.credits import live_billing

    return live_billing.bill_active_sessions()
