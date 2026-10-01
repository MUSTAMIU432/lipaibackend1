"""Infrastructure tasks shared by every module."""
from celery import shared_task


@shared_task(name="lipaidox.ping", ignore_result=False)
def ping() -> str:
    """Round-trip check for a running worker (`/health/?workers=1`, tests)."""
    return "pong"


@shared_task(name="lipaidox.content.publish_due_scheduled")
def publish_due_scheduled_task() -> int:
    """Beat job: publish scheduled posts whose time has passed."""
    from lipaidox.content.scheduling import publish_due_scheduled

    return publish_due_scheduled(throttle=False)
