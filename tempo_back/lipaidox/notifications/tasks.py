"""Background delivery for notifications."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="lipaidox.notifications.notify_new_content_posted")
def notify_new_content_posted_task(content_id) -> int:
    """
    Fan a newly published post out to the creator's audience: one in-app
    notification per follower/subscriber/member plus an Expo push. Runs off
    the publish request because the audience can be large and the push is an
    HTTP call. Safe to retry — the service claims `followers_notified`
    atomically, so a re-run never notifies twice.
    """
    from lipaidox.content.models import Content
    from lipaidox.notifications.services.content_notifications import notify_new_content_posted

    content = Content.objects.select_related("creator__user").filter(pk=content_id).first()
    if content is None:
        return 0
    return notify_new_content_posted(content)
