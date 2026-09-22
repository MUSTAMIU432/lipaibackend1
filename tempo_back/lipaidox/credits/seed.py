"""
Default Premium Live credit packages (PRD §3).

    100 credits = $10 = 15 min      (1 credit = $0.10 = 9 seconds)

Shared by the `seed_credit_packages` command and by the `creditPackages` query,
which creates them on first read when a database has none — a fresh deploy can
sell credits without anyone having to remember to run a command.
"""
from decimal import Decimal

from .models import CreditPackage, CreditPackageTarget, CreditType

# name, credits, price USD, minutes of Premium Live, badge
PACKS = [
    ("Starter", 100, "10.00", 15, ""),
    ("Standard", 500, "50.00", 75, ""),
    ("Pro", 1000, "100.00", 150, "Popular"),
    ("Premium", 2500, "250.00", 375, "Best value"),
]


def upsert_default_packages():
    """Create or reset the four standard packs. Returns [(package, created)]."""
    out = []
    for i, (name, credits, price, minutes, badge) in enumerate(PACKS):
        out.append(
            CreditPackage.objects.update_or_create(
                name=name,
                credit_type=CreditType.CREATOR_CREDIT,
                defaults={
                    "description": f"{credits:,} credits — {minutes} min of Premium Live",
                    "target": CreditPackageTarget.CREATOR,
                    "credit_amount": credits,
                    "bonus_credits": 0,
                    "price_usd": Decimal(price),
                    "duration_minutes": minutes,
                    "badge_label": badge,
                    "is_featured": badge == "Popular",
                    "is_active": True,
                    "sort_order": i,
                },
            )
        )
    return out


def ensure_default_packages():
    """
    Seed the standard packs only when no creator package exists AT ALL (active
    or not). An admin who has switched every pack off, or replaced them, keeps
    that choice — this never overwrites or resurrects anything.
    """
    if CreditPackage.objects.filter(credit_type=CreditType.CREATOR_CREDIT).exists():
        return False
    upsert_default_packages()
    return True
