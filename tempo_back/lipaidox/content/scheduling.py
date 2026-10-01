"""
Scheduled posts go live once their time has passed.

`scheduleContent` only records the time (status "scheduled" + `scheduled_at`).
Nothing used to act on it, and Render runs no Celery worker, so every
scheduled post stayed invisible forever. `publish_due_scheduled()` promotes
the due ones; it runs:

  * lazily, at the top of the feed / profile / post queries — so the moment
    anyone looks, overdue posts are live, worker or not;
  * every minute from Celery beat, where a worker exists;
  * on demand: `python manage.py publish_scheduled_content`.

Each post is flipped with a conditional UPDATE (`status="scheduled"`), so two
callers racing can't publish — or announce to followers — twice.
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger(__name__)

# The lazy path runs on every feed request; this keeps it to one cheap query
# per process every few seconds rather than one per request.
_THROTTLE_KEY = "content:publish-due-scheduled"
_THROTTLE_SECONDS = 10


def publish_due_scheduled(*, throttle: bool = True) -> int:
    """Publish every scheduled post whose time has come. Returns how many went live."""
    if throttle:
        try:
            if not cache.add(_THROTTLE_KEY, 1, _THROTTLE_SECONDS):
                return 0
        except Exception:  # cache down — still publish; correctness beats saving a query
            pass

    from lipaidox.content.models import Content
    from lipaidox.content.mutations.content_mutation import _announce_if_published

    now = timezone.now()
    due_ids = list(
        Content.objects.filter(status="scheduled", scheduled_at__lte=now).values_list("pk", flat=True)
    )
    published = 0
    for pk in due_ids:
        # Live at its scheduled time, not whenever someone happened to look —
        # the feed orders by published_at.
        claimed = Content.objects.filter(pk=pk, status="scheduled").update(
            status="published",
            published_at=Coalesce(F("published_at"), F("scheduled_at")),
            updated_at=now,
        )
        if not claimed:
            continue
        published += 1
        try:
            _announce_if_published(Content.objects.get(pk=pk))
        except Exception as exc:  # pragma: no cover - notifications are best-effort
            logger.warning("scheduled publish: follower fan-out skipped for %s: %s", pk, exc)
    if published:
        logger.info("Published %d scheduled post(s)", published)
    return published
