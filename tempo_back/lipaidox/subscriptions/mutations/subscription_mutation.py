import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ..models import Subscription, SubscriptionPayment, SubscriptionStatus, SubscriptionPaymentType, SubscriptionPaymentStatus
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.monetization.models import MonetizationSettings
from ..schema.subscription_schema import SubscriptionType
from lipaidox.auth.permissions import require_any_role

@strawberry.type
class SubscriptionMutation:
    @strawberry.mutation
    @require_any_role("fan", "creator", "admin")
    def subscribe_to_creator(
        self, info, creator_id: strawberry.ID,
        payment_source: str = "WALLET", method: Optional[str] = None,
        simulate: Optional[str] = None,
    ) -> SubscriptionType:
        user = info.context.request.user
        # Role validation handled by @require_any_role decorator

        # Accept either a CreatorProfile id or the creator's User id (the FE passes
        # a target user id from feed/profile cards).
        profile = (
            CreatorProfile.objects.filter(id=creator_id).first()
            or CreatorProfile.objects.filter(user_id=creator_id).first()
        )
        if profile is None:
            raise Exception("Creator not found")
        monetization = MonetizationSettings.objects.get(creator=profile)

        if not monetization.subscription_enabled:
            raise Exception("Subscriptions are not enabled for this creator")

        from decimal import Decimal
        from lipaidox.wallet.services import (
            settle, credit_fan_wallet, InsufficientFunds,
        )
        from lipaidox.wallet.models import TransactionType
        price = Decimal(str(monetization.subscription_price or 0))

        # Charge for the first period up front (gateway funds the wallet, wallet
        # is the spend source). Free-priced subs skip the money movement.
        if price > 0:
            if str(payment_source).upper() == "GATEWAY":
                from lipaidox.payment.gateways.registry import get_gateway
                from lipaidox.payment.models import ChargePurpose, ChargeStatus
                meta = {}
                if method:
                    meta["method"] = method
                if simulate:
                    meta["simulate"] = simulate
                charge = get_gateway().create_charge(
                    user=user, amount=price, purpose=ChargePurpose.SUBSCRIPTION, metadata=meta,
                )
                if charge.status != ChargeStatus.SUCCEEDED:
                    raise Exception("PAYMENT_FAILED")
                credit_fan_wallet(user, price)

        with transaction.atomic():
            # 1. Create or get existing subscription
            subscription, created = Subscription.objects.get_or_create(
                fan=user,
                creator=profile,
                defaults={
                    'price_at_signup': monetization.subscription_price,
                    'currency': monetization.display_currency if hasattr(monetization, 'display_currency') else 'USD',
                    'status': SubscriptionStatus.ACTIVE,
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30), # Default 30 days
                    'next_billing_date': timezone.now() + timedelta(days=30),
                }
            )

            if not created and subscription.status == SubscriptionStatus.ACTIVE:
                raise Exception("Already subscribed")

            # Reset status if it was cancelled/expired
            if not created:
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.price_at_signup = monetization.subscription_price
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
                subscription.save()

            # 2. Create Initial Payment row
            SubscriptionPayment.objects.create(
                subscription=subscription,
                fan=user,
                creator=profile,
                payment_type=SubscriptionPaymentType.INITIAL,
                payment_number=1,
                amount_paid=subscription.price_at_signup,
                net_amount=(
                    Decimal(str(subscription.price_at_signup))
                    * (Decimal("1") - (Decimal(str(subscription.platform_fee_percent)) / Decimal("100")))
                ),
                status=SubscriptionPaymentStatus.COMPLETED,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
                completed_at=timezone.now()
            )

            # 3. Move money: fan wallet -> creator wallet, net of platform fee.
            if price > 0:
                try:
                    settle(
                        fan_user=user, creator_profile=profile, gross=price,
                        fee_percent=subscription.platform_fee_percent,
                        tx_type=TransactionType.SUBSCRIPTION,
                        description=f"Subscription: {profile.username}",
                        subscription_payment_id=subscription.id,
                    )
                except InsufficientFunds:
                    raise Exception("INSUFFICIENT_FUNDS")

        return SubscriptionType.from_model(subscription)

    @strawberry.mutation
    @require_any_role("fan", "creator", "admin")
    def cancel_subscription(self, info, subscription_id: strawberry.ID) -> SubscriptionType:
        user = info.context.request.user
        # Role validation handled by @require_any_role decorator
        subscription = Subscription.objects.get(id=subscription_id, fan=user)

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancel_at_period_end = True
        subscription.save()

        return SubscriptionType.from_model(subscription)

    @strawberry.mutation
    @require_any_role("fan", "creator", "admin")
    def unsubscribe_from_creator(self, info, creator_id: strawberry.ID) -> bool:
        user = info.context.request.user
        try:
            subscription = Subscription.objects.get(
                fan=user, creator_id=creator_id, status=SubscriptionStatus.ACTIVE
            )
        except Subscription.DoesNotExist:
            return False
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancel_at_period_end = True
        subscription.save()
        return True
