"""
Seed the creator plan catalog — "Creators' Subscription Plans" (Free / Basic /
Go Plus / Premium). Idempotent: rows are upserted by tier, and the retired
Promax+ tier is switched off rather than deleted so old subscriptions resolve.

Convention for the numeric caps: None = unlimited, 0 = not allowed.

Run:  ./myenv/bin/python seed_plans.py
"""
import os
import sys

import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lipaidox_backend.settings')
django.setup()

from decimal import Decimal

from lipaidox.creator_plans.models import CreatorPlan
from lipaidox.creator_plans.constants import CreatorPlanTier

PLANS = [
    {
        'tier': CreatorPlanTier.FREE,
        'name': 'Free',
        'description': 'Create — start creating, build an audience, and experience the platform.',
        'price_per_month': Decimal('0.00'),
        'annual_discount_percent': Decimal('0'),
        'can_monetize': False, 'can_live_stream': False, 'can_sell_ppv': False,
        'can_receive_tips': False, 'can_sell_subscriptions': False, 'can_sell_custom_content': False,
        'monthly_free_credits': 0, 'unlimited_live_sessions': 0,
        'max_content_uploads_per_month': 2,
        'max_premium_content_per_month': 0,
        'max_live_countries': 0,
        'max_subscription_tiers': 0,
        'platform_fee_percent': None,
        'sort_order': 1,
    },
    {
        'tier': CreatorPlanTier.BASIC,
        'name': 'Basic',
        'description': 'Monetize — start earning from Premium Content.',
        'price_per_month': Decimal('5.99'),
        'annual_discount_percent': Decimal('10'),   # $64.69 billed annually
        'can_monetize': True, 'can_live_stream': True, 'can_sell_ppv': True,
        'can_receive_tips': True, 'can_sell_subscriptions': False, 'can_sell_custom_content': False,
        'monthly_free_credits': 0, 'unlimited_live_sessions': 0,
        'max_content_uploads_per_month': None,
        'max_premium_content_per_month': 2,
        'max_live_countries': 3,
        'max_subscription_tiers': 0,
        'platform_fee_percent': Decimal('30.00'),
        'sort_order': 2,
    },
    {
        'tier': CreatorPlanTier.GO_PLUS,
        'name': 'Go Plus',
        'description': 'Grow & Earn — grow your audience and build multiple income streams.',
        'price_per_month': Decimal('11.99'),
        'annual_discount_percent': Decimal('15'),   # $122.30 billed annually
        'can_monetize': True, 'can_live_stream': True, 'can_sell_ppv': True,
        'can_receive_tips': True, 'can_sell_subscriptions': True, 'can_sell_custom_content': True,
        'monthly_free_credits': 50, 'unlimited_live_sessions': 0,
        'max_content_uploads_per_month': None,
        'max_premium_content_per_month': 7,
        'max_live_countries': 5,
        'max_subscription_tiers': 1,
        'platform_fee_percent': Decimal('25.00'),
        'sort_order': 3,
    },
    {
        'tier': CreatorPlanTier.PREMIUM,
        'name': 'Premium',
        'description': 'Professional Creator — maximize monetization, reach and audience loyalty.',
        'price_per_month': Decimal('19.99'),
        'annual_discount_percent': Decimal('20'),   # $191.90 billed annually
        'can_monetize': True, 'can_live_stream': True, 'can_sell_ppv': True,
        'can_receive_tips': True, 'can_sell_subscriptions': True, 'can_sell_custom_content': True,
        'monthly_free_credits': 100, 'unlimited_live_sessions': 0,
        'max_content_uploads_per_month': None,
        'max_premium_content_per_month': None,
        'max_live_countries': None,     # "10+ countries"
        'max_subscription_tiers': 2,
        'platform_fee_percent': Decimal('20.00'),
        'sort_order': 4,
    },
]


def seed():
    for data in PLANS:
        data = {**data, 'is_active': True}
        CreatorPlan.objects.update_or_create(tier=data['tier'], defaults=data)

    retired = CreatorPlan.objects.filter(tier=CreatorPlanTier.PROMAX).update(is_active=False)
    print(f"✅ Creator plans seeded ({len(PLANS)} active, {retired} retired).")


if __name__ == "__main__":
    seed()
