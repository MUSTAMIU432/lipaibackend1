"""
Caching and background work against the real GraphQL schema and database.

    ./test.sh db lipaidox.tests_caching

Needs PostgreSQL (schema-isolated runner). Each test opts in to an in-memory
cache; `captureOnCommitCallbacks(execute=True)` stands in for the commit that
a TestCase never performs, so after-commit invalidation and enqueueing run.
"""
from decimal import Decimal as D
from types import SimpleNamespace as NS
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.cache import caches
from django.test import TestCase, override_settings

from lipaidox.auth.models import User
from lipaidox.content.models import Content, ContentStatus
from lipaidox.content_classification.models import PlatformCategory
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.credits.models import CreditPackage, CreditType
from lipaidox.payment.models import MobileMoneyProvider
from lipaidox_backend.schema import schema

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "caching-tests"}}


def gql(user, query, variables=None):
    request = NS(user=user or AnonymousUser(), META={"REMOTE_ADDR": "10.0.0.9", "HTTP_USER_AGENT": "tests"})
    result = schema.execute_sync(query, variable_values=variables or {}, context_value=NS(request=request))
    assert not result.errors, [str(e) for e in result.errors]
    return result.data


@override_settings(CACHES=LOCMEM)
class CatalogCacheTests(TestCase):
    PACKAGES = '{ creditPackages(creditType: "fan_credit") { name priceUsd } }'

    def setUp(self):
        caches["default"].clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.pack = CreditPackage.objects.create(
                name="Fan 100", credit_type=CreditType.FAN_CREDIT, credit_amount=100, price_usd=D("4.99"),
            )

    def packages(self):
        return gql(None, self.PACKAGES)["creditPackages"]

    def test_second_read_is_served_from_cache(self):
        self.assertEqual(self.packages(), [{"name": "Fan 100", "priceUsd": "4.99"}])
        with self.assertNumQueries(0):
            self.assertEqual(self.packages(), [{"name": "Fan 100", "priceUsd": "4.99"}])

    def test_update_invalidates(self):
        self.packages()
        with self.captureOnCommitCallbacks(execute=True):
            self.pack.price_usd = D("5.99")
            self.pack.save()
        self.assertEqual(self.packages()[0]["priceUsd"], "5.99")

    def test_delete_invalidates(self):
        self.packages()
        with self.captureOnCommitCallbacks(execute=True):
            self.pack.delete()
        self.assertEqual(self.packages(), [])

    def test_create_invalidates_categories(self):
        query = "{ allCategories { slug } }"
        self.assertEqual(gql(None, query)["allCategories"], [])
        with self.captureOnCommitCallbacks(execute=True):
            PlatformCategory.objects.create(name="Music", slug="music")
        self.assertEqual(gql(None, query)["allCategories"], [{"slug": "music"}])

    def test_mobile_money_providers_cached_and_invalidated(self):
        query = "{ mobileMoneyProviders { providerName } }"
        with self.captureOnCommitCallbacks(execute=True):
            p = MobileMoneyProvider.objects.create(provider_name="M-Pesa", country_name="Tanzania", country_code="TZ", dial_code="+255")
        self.assertEqual(gql(None, query)["mobileMoneyProviders"], [{"providerName": "M-Pesa"}])
        with self.assertNumQueries(0):
            gql(None, query)
        with self.captureOnCommitCallbacks(execute=True):
            p.is_active = False
            p.save()
        self.assertEqual(gql(None, query)["mobileMoneyProviders"], [])


@override_settings(CACHES=LOCMEM)
class ReviewSummaryCacheTests(TestCase):
    SUMMARY = "query($id: ID!) { reviewSummary(targetUserId: $id) { totalReviews averageRating } }"

    def setUp(self):
        caches["default"].clear()
        self.creator = User.objects.create_user(username="cr", email="cr@example.com", password="x", role="creator")
        CreatorProfile.objects.create(user=self.creator, username="cr")
        self.fan = User.objects.create_user(username="fan", email="fan@example.com", password="x")

    def summary(self):
        return gql(self.fan, self.SUMMARY, {"id": str(self.creator.id)})["reviewSummary"]

    def create_review(self, rating):
        with self.captureOnCommitCallbacks(execute=True):
            data = gql(
                self.fan,
                "mutation($id: ID!, $r: Int!) { createReview(targetUserId: $id, rating: $r, body: \"Great creator, really\") { review { id } } }",
                {"id": str(self.creator.id), "r": rating},
            )
        return data["createReview"]["review"]["id"]

    def test_create_update_delete_each_invalidate(self):
        self.assertEqual(self.summary()["totalReviews"], 0)
        review_id = self.create_review(4)
        self.assertEqual(self.summary(), {"totalReviews": 1, "averageRating": 4.0})

        with self.captureOnCommitCallbacks(execute=True):
            gql(self.fan, "mutation($id: ID!) { updateReview(reviewId: $id, rating: 2) { review { id } } }", {"id": review_id})
        self.assertEqual(self.summary()["averageRating"], 2.0)

        with self.captureOnCommitCallbacks(execute=True):
            gql(self.fan, "mutation($id: ID!) { deleteReview(reviewId: $id) { success } }", {"id": review_id})
        self.assertEqual(self.summary()["totalReviews"], 0)


@override_settings(CACHES=LOCMEM)
class SensitiveDataNotCachedTests(TestCase):
    def test_private_payout_and_tax_queries_leave_cache_empty(self):
        caches["default"].clear()
        user = User.objects.create_user(username="c9", email="c9@example.com", password="x", role="creator")
        CreatorProfile.objects.create(user=user, username="c9")
        gql(user, "{ myPaymentMethods { id } myTaxInformation { id } myCreatorEligibility { percent } }")
        self.assertEqual(len(caches["default"]._cache), 0)


class BackgroundWorkTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="c2", email="c2@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=user, username="c2")

    def test_publishing_queues_fan_out_after_commit(self):
        from lipaidox.content.mutations.content_mutation import _announce_if_published

        post = Content.objects.create(creator=self.profile, title="Hi", status=ContentStatus.PUBLISHED)
        with mock.patch("lipaidox.tasking.enqueue") as enqueue:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                _announce_if_published(post)
            enqueue.assert_not_called()  # nothing leaves before commit
            for cb in callbacks:
                cb()
        [call] = enqueue.call_args_list
        self.assertEqual(call.args[0].name, "lipaidox.notifications.notify_new_content_posted")
        self.assertEqual(call.args[1:], (str(post.pk),))

    def test_drafts_and_announced_posts_are_not_queued(self):
        from lipaidox.content.mutations.content_mutation import _announce_if_published

        draft = Content.objects.create(creator=self.profile, title="D", status=ContentStatus.DRAFT)
        done = Content.objects.create(creator=self.profile, title="A", status=ContentStatus.PUBLISHED, followers_notified=True)
        with mock.patch("lipaidox.tasking.enqueue") as enqueue, self.captureOnCommitCallbacks(execute=True):
            _announce_if_published(draft)
            _announce_if_published(done)
        enqueue.assert_not_called()

    def test_fan_out_task_claims_the_post_once(self):
        from lipaidox.notifications.tasks import notify_new_content_posted_task

        post = Content.objects.create(creator=self.profile, title="Hi", status=ContentStatus.PUBLISHED)
        notify_new_content_posted_task.apply(args=[str(post.pk)]).get()
        post.refresh_from_db()
        self.assertTrue(post.followers_notified)
        self.assertEqual(notify_new_content_posted_task.apply(args=[str(post.pk)]).get(), 0)

    def test_live_billing_beat_task_runs(self):
        from lipaidox.credits.tasks import bill_live_sessions_task

        summary = bill_live_sessions_task.apply().get()
        self.assertEqual(set(summary), {"billed", "ended_exhausted", "ended_lost"})
