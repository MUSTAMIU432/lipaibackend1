import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lipaidox_backend.settings')
django.setup()

from lipaidox.creator_plans.models import CreatorPlan
from lipaidox.creator_plans.constants import CreatorPlanTier

def seed():
    plans_data = [
        {
            'tier': CreatorPlanTier.FREE,
            'name': 'Free',
            'price_per_month': 0.00,
            'can_monetize': False,
            'can_live_stream': False,
            'can_sell_ppv': False,
            'can_receive_tips': False,
            'can_sell_subscriptions': False,
            'can_sell_custom_content': False,
            'monthly_free_credits': 0,
            'unlimited_live_sessions': 0,
            'sort_order': 1
        },
        {
            # 'basic' isn't in CreatorPlanTier choices (choices aren't DB-enforced);
            # stored as a plain string so the catalog matches the SPA's four tiers.
            'tier': 'basic',
            'name': 'Basic',
            'price_per_month': 9.99,
            'can_monetize': True,
            'can_live_stream': True,
            'can_sell_ppv': True,
            'can_receive_tips': True,
            'can_sell_subscriptions': False,
            'can_sell_custom_content': False,
            'monthly_free_credits': 0,
            'unlimited_live_sessions': 0,
            'credit_top_up_price': 10.00,
            'credit_top_up_duration_mins': 15,
            'sort_order': 2
        },
        {
            'tier': CreatorPlanTier.PREMIUM,
            'name': 'Premium',
            'price_per_month': 19.99,
            'can_monetize': True,
            'can_live_stream': True,
            'can_sell_ppv': True,
            'can_receive_tips': True,
            'can_sell_subscriptions': True,
            'can_sell_custom_content': True,
            'monthly_free_credits': 0,
            'unlimited_live_sessions': 0,
            'credit_top_up_price': 10.00,
            'credit_top_up_duration_mins': 15,
            'sort_order': 2
        },
        {
            'tier': CreatorPlanTier.PROMAX,
            'name': 'Promax+',
            'price_per_month': 49.99,
            'can_monetize': True,
            'can_live_stream': True,
            'can_sell_ppv': True,
            'can_receive_tips': True,
            'can_sell_subscriptions': True,
            'can_sell_custom_content': True,
            'monthly_free_credits': 100,
            'unlimited_live_sessions': 5,
            'credit_top_up_price': 10.00,
            'credit_top_up_duration_mins': 15,
            'sort_order': 3
        }
    ]

    for data in plans_data:
        CreatorPlan.objects.update_or_create(
            tier=data['tier'],
            defaults=data
        )
    
    print("✅ Creator Plans seeded successfully.")

if __name__ == "__main__":
    seed()
