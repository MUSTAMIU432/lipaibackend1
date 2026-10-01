"""
Scheduled posts go live once their time passes — lazily from the feed, with
no worker needed — exactly once, at their scheduled time.

    ./test.sh db lipaidox.content.tests_scheduling
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from lipaidox.auth.models import User
from lipaidox.content.models import Content
from lipaidox.content.scheduling import publish_due_scheduled
from lipaidox.creator_profile.models import CreatorProfile

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "sched-tests"}}


@override_settings(CACHES=LOCMEM)
class PublishDueScheduledTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username="sch", email="sch@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=user, username="sch")
        now = timezone.now()
        self.due = Content.objects.create(
            creator=self.profile, title="Due", status="scheduled", scheduled_at=now - timedelta(hours=2)
        )
        self.future = Content.objects.create(
            creator=self.profile, title="Later", status="scheduled", scheduled_at=now + timedelta(days=1)
        )

    @mock.patch("lipaidox.content.mutations.content_mutation._announce_if_published")
    def test_overdue_post_goes_live_at_its_scheduled_time(self, announce):
        self.assertEqual(publish_due_scheduled(throttle=False), 1)
        self.due.refresh_from_db()
        self.future.refresh_from_db()
        self.assertEqual(self.due.status, "published")
        self.assertEqual(self.due.published_at, self.due.scheduled_at)
        self.assertEqual(self.future.status, "scheduled")
        announce.assert_called_once()

    @mock.patch("lipaidox.content.mutations.content_mutation._announce_if_published")
    def test_second_run_publishes_and_announces_nothing(self, announce):
        publish_due_scheduled(throttle=False)
        self.assertEqual(publish_due_scheduled(throttle=False), 0)
        announce.assert_called_once()

    def test_throttle_skips_back_to_back_runs(self):
        self.assertEqual(publish_due_scheduled(), 1)
        Content.objects.create(
            creator=self.profile, title="Due 2", status="scheduled", scheduled_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(publish_due_scheduled(), 0)  # within the throttle window
        self.assertEqual(publish_due_scheduled(throttle=False), 1)

    def test_feed_query_publishes_overdue_posts(self):
        from lipaidox.content.queries.content_query import ContentQuery

        with mock.patch("lipaidox.content.queries.content_query.get_current_tenant", return_value=None):
            rows = ContentQuery().all_public_content(info=None)
        self.assertIn(str(self.due.pk), [str(r.id) for r in rows])
