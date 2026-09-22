"""
Seed the Premium Live credit packages (PRD §3) and the fan-credit conversion rate.

    100 credits = $10 = 15 min      (1 credit = $0.10 = 9 seconds)

    Starter   100 credits   $10    15 min
    Standard  500 credits   $50    1h 15m
    Pro      1000 credits  $100    2h 30m
    Premium  2500 credits  $250    6h 15m

Packages live in the database so they can change without an app update.
Idempotent (update_or_create by name + type). The old integer-era live packs
("1 credit", "3 credits", ...) are switched off, not deleted.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from lipaidox.credits.models import CreditConversionRate, CreditPackage, CreditType
from lipaidox.credits.seed import upsert_default_packages

LEGACY = ["1 credit", "3 credits", "5 credits", "10 credits"]


class Command(BaseCommand):
    help = "Seed Premium Live credit packages and a fan-credit conversion rate."

    def handle(self, *args, **options):
        for obj, created in upsert_default_packages():
            self.stdout.write(
                ("Created " if created else "Updated ") + f"{obj.name} ({obj.credit_amount} credits, ${obj.price_usd})"
            )

        retired = CreditPackage.objects.filter(credit_type=CreditType.FAN_CREDIT, name__in=LEGACY).update(is_active=False)
        self.stdout.write(f"Retired {retired} legacy live pack(s).")

        rate, created = CreditConversionRate.objects.get_or_create(
            credit_type=CreditType.FAN_CREDIT,
            is_active=True,
            defaults={
                "credits_per_unit": 1,
                "currency": "USD",
                "monetary_value": Decimal("10"),
                "platform_fee_percent": Decimal("20"),
                "effective_from": timezone.now(),
            },
        )
        self.stdout.write(("Created " if created else "Exists ") + "fan-credit conversion rate")
        self.stdout.write(self.style.SUCCESS("Done seeding credit packages."))
