"""Infrastructure tasks shared by every module."""
from celery import shared_task


@shared_task(name="lipaidox.ping", ignore_result=False)
def ping() -> str:
    """Round-trip check for a running worker (`/health/?workers=1`, tests)."""
    return "pong"
