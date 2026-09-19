"""
Plan rules from "Creators' Subscription Plans": annual totals, monthly upload /
premium-content caps, and the per-plan platform fee.

Run (no DB needed): ./test.sh quick
"""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase

from .constants import CreatorPlanTier
from .models import CreatorPlan
from .services import annual_total, assert_can_create_content, platform_fee_percent_for


def plan(tier, monthly, discount, **caps):
    return CreatorPlan(
        tier=tier, name=tier.title(), price_per_month=Decimal(monthly),
        annual_discount_percent=Decimal(discount), **caps,
    )


class AnnualPriceTests(SimpleTestCase):
    """The totals printed in the plan sheet."""

    def test_basic(self):
        self.assertEqual(annual_total(plan("basic", "5.99", "10")), Decimal("64.69"))

    def test_go_plus(self):
        self.assertEqual(annual_total(plan("go_plus", "11.99", "15")), Decimal("122.30"))

    def test_premium(self):
        self.assertEqual(annual_total(plan("premium", "19.99", "20")), Decimal("191.90"))

    def test_free_is_zero(self):
        self.assertEqual(annual_total(plan("free", "0", "0")), Decimal("0.00"))


class LimitTests(SimpleTestCase):
    """`assert_can_create_content` against a plan and this month's usage."""

    def _check(self, p, access_type, *, month_total, month_premium):
        qs = mock.MagicMock()
        qs.count.return_value = month_total
        qs.exclude.return_value.count.return_value = month_premium
        with mock.patch("lipaidox.creator_plans.services.plan_for_creator", return_value=p), \
             mock.patch("lipaidox.content.models.Content.objects.filter", return_value=qs):
            assert_can_create_content(object(), access_type)

    def test_free_capped_at_two_uploads(self):
        free = plan("free", "0", "0", max_content_uploads_per_month=2, max_premium_content_per_month=0)
        self._check(free, "free", month_total=1, month_premium=0)  # ok
        with self.assertRaisesMessage(Exception, "allows 2 uploads per month"):
            self._check(free, "free", month_total=2, month_premium=0)

    def test_free_cannot_sell_premium(self):
        free = plan("free", "0", "0", max_content_uploads_per_month=2, max_premium_content_per_month=0)
        with self.assertRaisesMessage(Exception, "isn't available on the Free plan"):
            self._check(free, "one_time", month_total=0, month_premium=0)

    def test_basic_two_premium_items(self):
        basic = plan("basic", "5.99", "10", max_premium_content_per_month=2)
        self._check(basic, "one_time", month_total=5, month_premium=1)  # ok
        with self.assertRaisesMessage(Exception, "allows 2 premium content"):
            self._check(basic, "timed", month_total=5, month_premium=2)

    def test_go_plus_seven(self):
        gp = plan("go_plus", "11.99", "15", max_premium_content_per_month=7)
        self._check(gp, "one_time", month_total=20, month_premium=6)  # ok
        with self.assertRaises(Exception):
            self._check(gp, "one_time", month_total=20, month_premium=7)

    def test_premium_is_unlimited(self):
        prem = plan("premium", "19.99", "20", max_premium_content_per_month=None)
        self._check(prem, "one_time", month_total=500, month_premium=500)

    def test_free_content_is_not_counted_as_premium(self):
        basic = plan("basic", "5.99", "10", max_premium_content_per_month=2)
        self._check(basic, "free", month_total=50, month_premium=2)  # free post still fine


class PlatformFeeTests(SimpleTestCase):
    def test_fee_follows_plan_and_falls_back(self):
        for tier, fee in (("basic", "30.00"), ("go_plus", "25.00"), ("premium", "20.00")):
            with mock.patch(
                "lipaidox.creator_plans.services.plan_for_creator",
                return_value=plan(tier, "1", "0", platform_fee_percent=Decimal(fee)),
            ):
                self.assertEqual(platform_fee_percent_for(object(), Decimal("15")), Decimal(fee))
        with mock.patch(
            "lipaidox.creator_plans.services.plan_for_creator",
            return_value=plan("free", "0", "0", platform_fee_percent=None),
        ):
            self.assertEqual(platform_fee_percent_for(object(), Decimal("15")), Decimal("15"))


class TextPostLimitTests(SimpleTestCase):
    """200 words normally, 100 once a background is applied."""

    def setUp(self):
        from lipaidox.content.text_limits import assert_text_post_within_limit, word_limit_for
        self.check = assert_text_post_within_limit
        self.limit = word_limit_for

    def test_limits(self):
        self.assertEqual(self.limit(None), 200)
        self.assertEqual(self.limit({"mode": "styled", "backgroundId": "none"}), 200)
        self.assertEqual(self.limit({"mode": "styled", "backgroundId": "sunset"}), 100)
        self.assertEqual(self.limit({"backgroundId": "none", "backgroundImage": "x.jpg"}), 100)

    def test_enforced(self):
        self.check("word " * 200, None)  # exactly 200 is fine
        with self.assertRaisesMessage(Exception, "limited to 200 words"):
            self.check("word " * 201, None)
        self.check("word " * 100, {"backgroundId": "sunset"})
        with self.assertRaisesMessage(Exception, "limited to 100 words with a background"):
            self.check("word " * 101, {"backgroundId": "sunset"})
