"""
Plan rules the rest of the backend asks about: what a creator's plan allows, the
annual price, and the platform's cut of a sale.

Convention for every numeric cap on `CreatorPlan`: ``None`` means unlimited and
``0`` means not allowed.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .constants import CreatorPlanStatus, CreatorPlanTier
from .models import CreatorPlan, CreatorPlanSubscription

_CENT = Decimal("0.01")


def annual_total(plan: CreatorPlan) -> Decimal:
    """What a year up front costs: monthly x 12, less the plan's annual discount."""
    monthly = Decimal(str(plan.price_per_month or 0))
    discount = Decimal(str(plan.annual_discount_percent or 0))
    total = monthly * 12 * (Decimal("100") - discount) / Decimal("100")
    return total.quantize(_CENT, rounding=ROUND_HALF_UP)


def plan_for_creator(profile) -> CreatorPlan | None:
    """The plan a creator is on right now — Free once a paid period has lapsed."""
    tier = CreatorPlanTier.FREE
    sub = CreatorPlanSubscription.objects.filter(creator=profile).first()
    if sub and sub.status == CreatorPlanStatus.ACTIVE:
        expired = sub.current_period_end is not None and sub.current_period_end < timezone.now()
        if not expired:
            tier = sub.plan_tier
    return CreatorPlan.objects.filter(tier=tier).first()


def platform_fee_percent_for(profile, default: Decimal) -> Decimal:
    """The platform's cut of this creator's sales, or `default` if the plan sets none."""
    plan = plan_for_creator(profile)
    if plan is not None and plan.platform_fee_percent is not None:
        return Decimal(str(plan.platform_fee_percent))
    return default


def _month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def assert_can_create_content(profile, access_type: str) -> None:
    """
    Raise a user-facing error if creating this content would break the creator's
    plan limits: total uploads per month, and premium (paid) items per month.
    Drafts count, so saving a draft can't be used to dodge the cap.
    """
    from lipaidox.content.models import Content

    plan = plan_for_creator(profile)
    if plan is None:
        return  # No catalog seeded — don't block creators on missing config.

    this_month = Content.objects.filter(creator=profile, created_at__gte=_month_start())

    cap = plan.max_content_uploads_per_month
    if cap is not None and this_month.count() >= cap:
        raise Exception(
            f"The {plan.name} plan allows {cap} uploads per month and you've used them. "
            "Upgrade your plan to publish more."
        )

    if access_type and access_type != "free":
        prem_cap = plan.max_premium_content_per_month
        if prem_cap is not None:
            if prem_cap == 0:
                raise Exception(
                    f"Premium content isn't available on the {plan.name} plan. "
                    "Upgrade to Basic or higher to monetize."
                )
            used = this_month.exclude(access_type="free").count()
            if used >= prem_cap:
                raise Exception(
                    f"The {plan.name} plan allows {prem_cap} premium content items per month "
                    "and you've used them. Upgrade your plan for more."
                )
