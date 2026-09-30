"""
Abandoned live streams are ended before the Live tab lists them (needs the real
schema — run with `./test.sh db lipaidox.live_streaming.tests`).
"""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from lipaidox.auth.models import User
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.live_streaming.models import LiveStream, LiveStreamStatus
from lipaidox.live_streaming.queries.live_streaming_query import (
    ABANDONED_AFTER,
    _expire_abandoned_live_streams,
)


class AbandonedStreamTests(TestCase):
    def setUp(self):
        cache.clear()  # the sweep is throttled through the cache
        user = User.objects.create_user(username="c1", email="c1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=user, username="c1")

    def live(self, started_ago):
        return LiveStream.objects.create(
            creator=self.profile,
            title="s",
            status=LiveStreamStatus.LIVE,
            started_at=timezone.now() - started_ago,
            current_viewer_count=3,
        )

    def test_stream_live_past_the_limit_is_ended(self):
        old = self.live(ABANDONED_AFTER + timedelta(minutes=1))
        _expire_abandoned_live_streams()
        old.refresh_from_db()
        self.assertEqual(old.status, LiveStreamStatus.ENDED)
        self.assertEqual(old.end_reason, "connection_lost")
        self.assertEqual(old.current_viewer_count, 0)
        self.assertIsNotNone(old.ended_at)

    def test_recent_stream_stays_live(self):
        fresh = self.live(timedelta(minutes=5))
        _expire_abandoned_live_streams()
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, LiveStreamStatus.LIVE)

    # Test settings use DummyCache (stores nothing), which can't throttle.
    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_sweep_is_throttled(self):
        cache.clear()
        _expire_abandoned_live_streams()
        old = self.live(ABANDONED_AFTER + timedelta(minutes=1))
        _expire_abandoned_live_streams()  # within the throttle window: skipped
        old.refresh_from_db()
        self.assertEqual(old.status, LiveStreamStatus.LIVE)
