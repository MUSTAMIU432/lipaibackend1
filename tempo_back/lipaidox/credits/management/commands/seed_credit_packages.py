"""
Seed live-stream credit packages + a fan-credit conversion rate.

Package ids/amounts/prices mirror the frontend CREDIT_PACKS (lib/types.ts) so the
Buy Credits UI and the backend agree. Idempotent (update_or_create by name).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from lipaidox.credits.models import CreditPackage, CreditConversionRate, CreditType

PACKS = [
    {"name": "1 credit",  "credit_amount": 1,  "bonus_credits": 0, "price_usd": Decimal("10"), "duration_minutes": 15,  "badge_label": ""},
    {"name": "3 credits", "credit_amount": 3,  "bonus_credits": 0, "price_usd": Decimal("28"), "duration_minutes": 45,  "badge_label": "Popular"},
    {"name": "5 credits", "credit_amount": 5,  "bonus_credits": 0, "price_usd": Decimal("45"), "duration_minutes": 75,  "badge_label": ""},
    {"name": "10 credits","credit_amount": 10, "bonus_credits": 0, "price_usd": Decimal("85"), "duration_minutes": 150, "badge_label": ""},
]


class Command(BaseCommand):
    help = "Seed live-stream credit packages and a fan-credit conversion rate."

    def handle(self, *args, **options):
        for i, p in enumerate(PACKS):
            obj, created = CreditPackage.objects.update_or_create(
                name=p["name"],
                credit_type=CreditType.FAN_CREDIT,
                defaults={
                    "credit_amount": p["credit_amount"],
                    "bonus_credits": p["bonus_credits"],
                    "price_usd": p["price_usd"],
                    "duration_minutes": p["duration_minutes"],
                    "badge_label": p["badge_label"],
                    "is_featured": p["badge_label"] == "Popular",
                    "is_active": True,
                    "sort_order": i,
                },
            )
            self.stdout.write(("Created " if created else "Updated ") + f"{obj.name} (${obj.price_usd})")

        # One fan-credit conversion rate: 1 credit -> $10 gross, 20% platform fee.
        rate, created = CreditConversionRate.objects.get_or_create(
            credit_type=CreditType.FAN_CREDIT,
            is_active=True,
            defaults={
                "credits_per_unit": Decimal("1"),
                "currency": "USD",
                "monetary_value": Decimal("10"),
                "platform_fee_percent": Decimal("20"),
                "effective_from": timezone.now(),
            },
        )
        self.stdout.write(("Created " if created else "Exists ") + "fan-credit conversion rate")
        self.stdout.write(self.style.SUCCESS("Done seeding credit packages."))
