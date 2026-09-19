"""
Convert existing creator balances to the PRD rate.

Before: 1 credit = $10 = 15 minutes.   After: 100 credits = $10 = 15 minutes.
So a wallet holding 3 credits (45 min) now holds 300 (still 45 min). Buckets and
lifetime totals are multiplied by 100 and the change is recorded as ONE
ADJUSTMENT ledger row per wallet, so the ledger's before/after chain stays
unbroken and history is never rewritten.
"""
from decimal import Decimal

from django.db import migrations

FACTOR = Decimal("100")
BUCKETS = ("purchased_credits", "free_monthly_credits", "gifted_credits")
TOTALS = ("total_credits_used", "total_credits_purchased", "total_credits_gifted", "monthly_credits_allocated")


def convert(apps, schema_editor):
    Wallet = apps.get_model("lipaidox_credits", "CreatorCreditWallet")
    Ledger = apps.get_model("lipaidox_credits", "CreatorCreditLedger")
    for wallet in Wallet.objects.all():
        before = sum((getattr(wallet, f) for f in BUCKETS), Decimal("0"))
        for field in BUCKETS + TOTALS:
            setattr(wallet, field, getattr(wallet, field) * FACTOR)
        wallet.save()
        after = sum((getattr(wallet, f) for f in BUCKETS), Decimal("0"))
        if before != after:
            Ledger.objects.create(
                creator_id=wallet.creator_id,
                wallet=wallet,
                transaction_type="adjustment",
                credits_delta=after - before,
                credits_before=before,
                credits_after=after,
                description="Rate change: balance converted to 100 credits = $10 = 15 min",
                metadata={"conversion_factor": "100"},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("lipaidox_credits", "0002_livebillingevent_livecreditreservation_and_more"),
    ]

    operations = [
        # Not reversible on purpose: dividing back would rewrite ledger history.
        migrations.RunPython(convert, migrations.RunPython.noop),
    ]
