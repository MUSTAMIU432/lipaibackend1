import strawberry
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ..models import CreatorPlan, CreatorPlanSubscription, CreatorPlanPayment
from ..constants import PlanPaymentType, PlanPaymentStatus, CreatorPlanStatus
from ..schema.plan_schema import CreatorPlanSubscriptionType
from lipaidox.creator_profile.models import CreatorProfile


@strawberry.type
class PurchasePlanResult:
    """Outcome of a paid plan purchase — the fan wallet was actually debited."""
    success: bool
    code: str          # "OK" | "INSUFFICIENT_FUNDS" | "INVALID"
    message: str
    wallet_balance: float
    subscription: Optional[CreatorPlanSubscriptionType]


def _apply_plan_change(user, target_tier, target_plan, amount_paid, billing_period="monthly"):
    """
    Activate/refresh the creator's subscription, record the payment, and sync the
    profile cache. Assumes the caller already collected the money (or it's free)
    and is running inside a transaction.
    """
    profile, _ = CreatorProfile.objects.get_or_create(
        user=user,
        defaults={
            "username": getattr(user, "username", None) or f"user_{user.pk}",
            "tenant": getattr(user, "tenant", None),
        },
    )
    now = timezone.now()
    period_end = now + timedelta(days=365 if billing_period == "annual" else 30)

    sub, created = CreatorPlanSubscription.objects.get_or_create(
        creator=profile,
        defaults={
            "plan_tier": target_tier,
            "price_at_signup": target_plan.price_per_month,
            "status": CreatorPlanStatus.ACTIVE,
            "current_period_start": now,
            "current_period_end": period_end,
            "available_credits": target_plan.monthly_free_credits,
        },
    )
    if not created:
        sub.plan_tier = target_tier
        sub.price_at_signup = target_plan.price_per_month
        sub.status = CreatorPlanStatus.ACTIVE
        sub.current_period_start = now
        sub.current_period_end = period_end
        sub.available_credits = target_plan.monthly_free_credits  # reset/refresh on change
        sub.cancel_at_period_end = False
        sub.cancelled_at = None
        sub.save()

    CreatorPlanPayment.objects.create(
        creator=profile,
        plan_subscription=sub,
        plan_tier=target_tier,
        payment_type=PlanPaymentType.INITIAL if created else PlanPaymentType.UPGRADE,
        amount_paid=amount_paid,
        status=PlanPaymentStatus.COMPLETED,
        completed_at=now,
        period_start=sub.current_period_start,
        period_end=sub.current_period_end,
    )

    # Sync to profile (quick-look columns).
    profile.plan_tier = target_tier
    profile.plan_expires_at = sub.current_period_end
    profile.live_credits = sub.available_credits
    profile.save()
    return sub


@strawberry.type
class CreatorPlanMutation:
    @strawberry.mutation
    def purchase_creator_plan(
        self, info, target_tier: str, billing_period: str = "monthly",
    ) -> PurchasePlanResult:
        """
        Buy/renew a creator plan by SPENDING the fan wallet (funded beforehand via
        the gateway), then activate the subscription. This is the real,
        money-moving path — unlike `upgrade_plan`, which only records a subscription.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Auth required")

        from lipaidox.wallet.services import (
            spend_fan_to_platform, get_or_create_fan_wallet, InsufficientFunds,
        )
        from lipaidox.wallet.models import TransactionType

        def _bal():
            return float(get_or_create_fan_wallet(user).balance)

        def _result(success, code, message, subscription=None):
            return PurchasePlanResult(
                success=success, code=code, message=message,
                wallet_balance=_bal(), subscription=subscription,
            )

        try:
            target_plan = CreatorPlan.objects.get(tier=target_tier)
        except CreatorPlan.DoesNotExist:
            return _result(False, "INVALID", "Unknown plan tier")

        monthly = Decimal(str(target_plan.price_per_month or 0))

        # Free or zero-priced tier — no charge, apply directly.
        if target_tier == "free" or monthly <= 0:
            try:
                with transaction.atomic():
                    sub = _apply_plan_change(user, target_tier, target_plan, Decimal("0.00"), billing_period)
            except Exception as exc:  # noqa: BLE001 - surface a clean message
                return _result(False, "INVALID", str(exc))
            return _result(True, "OK", "Plan updated", CreatorPlanSubscriptionType.from_model(sub))

        # Amount due mirrors the SPA's annual discount math (20% off, billed x12).
        if billing_period == "annual":
            per = (monthly * Decimal("0.8")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            amount = (per * 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            amount = monthly.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Debit the wallet and activate in one transaction — a failure rolls back
        # the charge too, so we never take money without granting the plan.
        try:
            with transaction.atomic():
                spend_fan_to_platform(
                    fan_user=user,
                    amount=amount,
                    tx_type=TransactionType.SUBSCRIPTION,
                    description=f"Creator plan: {target_plan.name} ({billing_period})",
                )
                sub = _apply_plan_change(user, target_tier, target_plan, amount, billing_period)
        except InsufficientFunds:
            return _result(False, "INSUFFICIENT_FUNDS", "Insufficient wallet balance. Top up to continue.")

        return _result(True, "OK", "Plan activated", CreatorPlanSubscriptionType.from_model(sub))

    @strawberry.mutation
    def upgrade_plan(self, info, target_tier: str) -> CreatorPlanSubscriptionType:
        user = info.context.request.user
        if not user.is_authenticated: raise Exception("Auth required")

        profile = CreatorProfile.objects.get(user=user)
        target_plan = CreatorPlan.objects.get(tier=target_tier)

        with transaction.atomic():
            sub, created = CreatorPlanSubscription.objects.get_or_create(
                creator=profile,
                defaults={
                    'plan_tier': target_tier,
                    'price_at_signup': target_plan.price_per_month,
                    'status': CreatorPlanStatus.ACTIVE,
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30),
                    'available_credits': target_plan.monthly_free_credits,
                }
            )

            if not created:
                sub.plan_tier = target_tier
                sub.price_at_signup = target_plan.price_per_month
                sub.status = CreatorPlanStatus.ACTIVE
                sub.current_period_start = timezone.now()
                sub.current_period_end = timezone.now() + timedelta(days=30)
                sub.available_credits = target_plan.monthly_free_credits # Reset/Add credits on upgrade
                sub.save()

            # Record payment
            CreatorPlanPayment.objects.create(
                creator=profile,
                plan_subscription=sub,
                plan_tier=target_tier,
                payment_type=PlanPaymentType.UPGRADE if not created else PlanPaymentType.INITIAL,
                amount_paid=target_plan.price_per_month,
                status=PlanPaymentStatus.COMPLETED,
                completed_at=timezone.now(),
                period_start=sub.current_period_start,
                period_end=sub.current_period_end
            )

            # Sync to profile (Cache/Quick look column)
            profile.plan_tier = target_tier
            profile.plan_expires_at = sub.current_period_end
            profile.live_credits = sub.available_credits
            profile.save()

        return CreatorPlanSubscriptionType.from_model(sub)

    @strawberry.mutation
    def cancel_plan(self, info) -> CreatorPlanSubscriptionType:
        user = info.context.request.user
        profile = CreatorProfile.objects.get(user=user)
        sub = CreatorPlanSubscription.objects.get(creator=profile)

        sub.status = CreatorPlanStatus.CANCELLED
        sub.cancelled_at = timezone.now()
        sub.cancel_at_period_end = True
        sub.save()

        return CreatorPlanSubscriptionType.from_model(sub)
