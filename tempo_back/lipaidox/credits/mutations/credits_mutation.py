import enum
import strawberry
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from typing import Optional, List
from decimal import Decimal
from ..models import (
    CreditPackage, CreditConversionRate, CreditPurchase, CreditGift,
    CreatorCreditWallet, CreatorCreditLedger,
    FanCreditWallet, FanCreditLedger, FanCreditGiftSent,
    CreditType, CreditTransactionType, CreditTransactionStatus,
    CreditGiftStatus, GiftAnimationType
)
from ..schema.credits_schema import (
    CreditPackageType, CreditConversionRateType, CreditPurchaseType,
    CreditGiftType, CreatorCreditWalletType, CreatorCreditLedgerType,
    FanCreditWalletType, FanCreditLedgerType, FanCreditGiftSentType,
    PurchaseCreditsInput, GiftCreditsInput, SendGiftInput,
    UseCreatorCreditsInput, CreateCreditPackageInput, UpdateCreditPackageInput,
    CreateConversionRateInput
)
from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_creator(user):
    """Check if user is a creator"""
    if user.role != UserRoles.CREATOR:
        raise Exception("Creator access required")
    return True


def require_admin(user):
    """Check if user is an admin"""
    if user.role not in [UserRoles.ADMIN, 'superadmin']:
        raise Exception("Admin access required")
    return True


@strawberry.enum
class CreditPaymentSource(enum.Enum):
    WALLET = "wallet"
    GATEWAY = "gateway"


@strawberry.type
class PurchaseCreditPackResult:
    success: bool
    code: str          # "OK" | "INSUFFICIENT_FUNDS" | "PAYMENT_FAILED" | "INVALID"
    message: str
    credit_balance: int
    wallet_balance: float


@strawberry.type
class CreditsMutation:
    @strawberry.mutation
    def purchase_credit_pack(
        self,
        info: strawberry.types.Info,
        package_id: strawberry.ID,
        payment_source: CreditPaymentSource = CreditPaymentSource.WALLET,
        method: Optional[str] = None,
        simulate: Optional[str] = None,
    ) -> PurchaseCreditPackResult:
        """Buy a credit pack with real money (wallet or gateway) and deposit the
        credits (incl. bonus) into the fan credit wallet."""
        user = require_auth(info)
        from lipaidox.wallet.services import (
            spend_fan_to_platform, credit_fan_wallet, get_or_create_fan_wallet,
            InsufficientFunds,
        )
        from lipaidox.wallet.models import TransactionType

        def _money():
            return float(get_or_create_fan_wallet(user).balance)

        def _credits():
            w, _ = FanCreditWallet.objects.get_or_create(fan=user)
            return int(w.total_available_credits)

        try:
            package = CreditPackage.objects.get(id=package_id, is_active=True)
        except CreditPackage.DoesNotExist:
            return PurchaseCreditPackResult(
                success=False, code="INVALID", message="Package not found",
                credit_balance=_credits(), wallet_balance=_money(),
            )

        price = Decimal(str(package.price_usd))

        # GATEWAY: charge the provider then fund the wallet (top-up-then-spend).
        if payment_source == CreditPaymentSource.GATEWAY:
            from lipaidox.payment.gateways.registry import get_gateway
            from lipaidox.payment.models import ChargePurpose, ChargeStatus
            meta = {}
            if method:
                meta["method"] = method
            if simulate:
                meta["simulate"] = simulate
            charge = get_gateway().create_charge(
                user=user, amount=price, purpose=ChargePurpose.CREDITS, metadata=meta,
            )
            if charge.status != ChargeStatus.SUCCEEDED:
                return PurchaseCreditPackResult(
                    success=False, code="PAYMENT_FAILED", message="Payment failed",
                    credit_balance=_credits(), wallet_balance=_money(),
                )
            credit_fan_wallet(user, price)

        try:
            with transaction.atomic():
                purchase = CreditPurchase.objects.create(
                    user=user, credit_type=package.credit_type,
                    package=package, credits_purchased=package.credit_amount,
                    bonus_credits=package.bonus_credits, total_credits=package.total_credits,
                    amount_paid=price, currency="USD", status=CreditTransactionStatus.PENDING,
                )
                # Debit the money wallet for the pack.
                spend_fan_to_platform(
                    fan_user=user, amount=price, tx_type=TransactionType.CREDIT_PURCHASE,
                    description=f"Credit pack: {package.name}", credit_purchase_id=purchase.id,
                )
                wallet, _ = FanCreditWallet.objects.get_or_create(fan=user)
                wallet.add_purchased_credits(package.total_credits, purchase.id)
                purchase.status = CreditTransactionStatus.COMPLETED
                purchase.completed_at = timezone.now()
                purchase.save()
        except InsufficientFunds:
            return PurchaseCreditPackResult(
                success=False, code="INSUFFICIENT_FUNDS",
                message="Insufficient wallet balance. Top up to continue.",
                credit_balance=_credits(), wallet_balance=_money(),
            )

        return PurchaseCreditPackResult(
            success=True, code="OK", message="Credits added",
            credit_balance=_credits(), wallet_balance=_money(),
        )

    # Credit Purchase Mutations
    @strawberry.mutation
    def purchase_credits(self, info: strawberry.types.Info, input: PurchaseCreditsInput) -> CreditPurchaseType:
        """Purchase a credit package"""
        user = require_auth(info)

        try:
            package = CreditPackage.objects.get(id=input.packageId, is_active=True)
        except CreditPackage.DoesNotExist:
            raise Exception("Credit package not found or inactive")

        with transaction.atomic():
            # Create purchase record
            purchase = CreditPurchase.objects.create(
                user=user,
                tenant=user.tenant,
                credit_type=package.credit_type,
                package=package,
                credits_purchased=package.credit_amount,
                bonus_credits=package.bonus_credits,
                total_credits=package.total_credits,
                amount_paid=package.price_usd,
                currency='USD',
                status=CreditTransactionStatus.PENDING
            )

            # Credit the appropriate wallet
            if package.credit_type == CreditType.CREATOR_CREDIT:
                from lipaidox.creator_profile.models import CreatorProfile
                try:
                    profile = CreatorProfile.objects.get(user=user)
                    wallet, created = CreatorCreditWallet.objects.get_or_create(
                        creator=profile,
                        defaults={'tenant': user.tenant}
                    )
                    wallet.add_purchased_credits(package.total_credits, purchase.id)
                except CreatorProfile.DoesNotExist:
                    raise Exception("Creator profile not found")
            else:
                wallet, created = FanCreditWallet.objects.get_or_create(
                    fan=user,
                    defaults={'tenant': user.tenant}
                )
                wallet.add_purchased_credits(package.total_credits, purchase.id)

            # Mark purchase as completed
            purchase.status = CreditTransactionStatus.COMPLETED
            purchase.completed_at = timezone.now()
            purchase.save()

        return CreditPurchaseType.from_model(purchase)

    # Admin Gift Mutations
    @strawberry.mutation
    def gift_credits(self, info: strawberry.types.Info, input: GiftCreditsInput) -> CreditGiftType:
        """Admin gifts credits to a user (admin only)"""
        user = require_auth(info)
        require_admin(user)

        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_gift_credits:
            raise Exception("Permission denied: can_gift_credits required")

        from lipaidox.auth.models import User
        try:
            target_user = User.objects.get(id=input.userId)
        except User.DoesNotExist:
            raise Exception("User not found")

        with transaction.atomic():
            # Create gift record
            gift = CreditGift.objects.create(
                gifted_to_user=target_user,
                gifted_by_admin=admin_account,
                tenant=user.tenant,
                credit_type=input.creditType,
                credits_amount=input.creditsAmount,
                reason=input.reason,
                internal_note=input.internalNote,
                expires_at=input.expiresAt,
                status=CreditGiftStatus.PENDING
            )

            # Deliver credits to appropriate wallet
            if input.creditType == CreditType.CREATOR_CREDIT:
                from lipaidox.creator_profile.models import CreatorProfile
                try:
                    profile = CreatorProfile.objects.get(user=target_user)
                    wallet, created = CreatorCreditWallet.objects.get_or_create(
                        creator=profile,
                        defaults={'tenant': user.tenant}
                    )
                    wallet.add_gifted_credits(input.creditsAmount, gift.id, input.expiresAt)
                except CreatorProfile.DoesNotExist:
                    raise Exception("Target user is not a creator")
            else:
                wallet, created = FanCreditWallet.objects.get_or_create(
                    fan=target_user,
                    defaults={'tenant': user.tenant}
                )
                wallet.add_gifted_credits(input.creditsAmount, gift.id)

            # Mark gift as delivered
            gift.status = CreditGiftStatus.DELIVERED
            gift.delivered_at = timezone.now()
            gift.save()

        return CreditGiftType.from_model(gift)

    # Fan Gift Sending Mutations
    @strawberry.mutation
    def send_gift_to_creator(self, info: strawberry.types.Info, input: SendGiftInput) -> FanCreditGiftSentType:
        """Fan sends credits as gift to creator during live stream"""
        user = require_auth(info)

        # Get fan wallet
        wallet, created = FanCreditWallet.objects.get_or_create(fan=user)

        if not wallet.has_sufficient_credits(input.creditsAmount):
            raise Exception("Insufficient credits")

        from lipaidox.creator_profile.models import CreatorProfile
        try:
            creator = CreatorProfile.objects.get(id=input.creatorId)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator not found")

        # Get active conversion rate
        conversion_rate = None
        try:
            conversion_rate = CreditConversionRate.objects.filter(
                credit_type=CreditType.FAN_CREDIT,
                is_active=True,
                effective_from__lte=timezone.now()
            ).filter(
                Q(effective_until__isnull=True) | Q(effective_until__gt=timezone.now())
            ).first()
        except:
            pass

        with transaction.atomic():
            # Create gift sent record
            gift_sent = FanCreditGiftSent.objects.create(
                fan=user,
                creator=creator,
                fan_wallet=wallet,
                live_stream_id=input.liveStreamId,
                credits_sent=input.creditsAmount,
                animation_type=input.animationType or GiftAnimationType.HEART,
                message=input.message,
                is_anonymous=input.isAnonymous,
                conversion_rate=conversion_rate,
                status=CreditGiftStatus.PENDING
            )

            # Calculate money earnings from the gifted credits (net of platform fee).
            earnings = gift_sent.calculate_earnings() if conversion_rate else None

            # Deduct credits from fan wallet
            if not wallet.use_credits(input.creditsAmount, gift_sent.id):
                raise Exception("Failed to deduct credits")

            # Mark as delivered
            gift_sent.status = CreditGiftStatus.DELIVERED
            gift_sent.delivered_at = timezone.now()
            gift_sent.save()

            # Pay the creator: credit their money wallet + write a tip ledger row.
            # Credits were already paid for at buy-time, so this is a credit-funded
            # earning (no fan money wallet debit here).
            net_payout = (earnings or {}).get("creator_earnings") if earnings else None
            if net_payout and net_payout > 0:
                try:
                    from lipaidox.wallet.services import credit_creator_from_credits
                    credit_creator_from_credits(
                        fan_user=user,
                        creator_profile=creator,
                        gross=net_payout,
                        fee_percent=0,  # creator_earnings is already net of platform fee
                        description="Live gift",
                        tip_id=gift_sent.id,
                    )
                except Exception:
                    pass

        return FanCreditGiftSentType.from_model(gift_sent)

    # Creator Credit Usage Mutations
    @strawberry.mutation
    def use_creator_credits(self, info: strawberry.types.Info, input: UseCreatorCreditsInput) -> CreatorCreditLedgerType:
        """Creator uses credits for live streaming"""
        user = require_auth(info)
        require_creator(user)

        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator profile not found")

        try:
            wallet = CreatorCreditWallet.objects.get(creator=profile)
        except CreatorCreditWallet.DoesNotExist:
            raise Exception("Credit wallet not found")

        if not wallet.has_sufficient_credits(input.creditsAmount):
            raise Exception("Insufficient credits. Please purchase more credits.")

        # Use credits
        wallet.use_credits(input.creditsAmount, input.liveStreamId)

        # Return the latest ledger entry
        ledger_entry = CreatorCreditLedger.objects.filter(
            creator=profile,
            live_stream_id=input.liveStreamId
        ).order_by('-created_at').first()

        return CreatorCreditLedgerType.from_model(ledger_entry)

    @strawberry.mutation
    def allocate_monthly_credits(self, info: strawberry.types.Info, creatorId: strawberry.ID, amount: int) -> CreatorCreditWalletType:
        """Allocate monthly free credits to a creator (admin only)"""
        user = require_auth(info)
        require_admin(user)

        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(id=creatorId)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator not found")

        wallet, created = CreatorCreditWallet.objects.get_or_create(
            creator=profile,
            defaults={'tenant': user.tenant}
        )

        wallet.allocate_monthly_credits(amount)
        return CreatorCreditWalletType.from_model(wallet)

    # Credit Package Admin Mutations
    @strawberry.mutation
    def create_credit_package(self, info: strawberry.types.Info, input: CreateCreditPackageInput) -> CreditPackageType:
        """Create a new credit package (admin only)"""
        user = require_auth(info)
        require_admin(user)

        package = CreditPackage.objects.create(
            name=input.name,
            description=input.description,
            credit_type=input.creditType,
            target=input.target or 'both',
            credit_amount=input.creditAmount,
            price_usd=input.priceUsd,
            bonus_credits=input.bonusCredits or 0,
            duration_minutes=input.durationMinutes,
            is_featured=input.isFeatured,
            is_active=input.isActive,
            sort_order=input.sortOrder or 0,
            badge_label=input.badgeLabel
        )

        return CreditPackageType.from_model(package)

    @strawberry.mutation
    def update_credit_package(
        self,
        info: strawberry.types.Info,
        packageId: strawberry.ID,
        input: UpdateCreditPackageInput
    ) -> CreditPackageType:
        """Update an existing credit package (admin only)"""
        user = require_auth(info)
        require_admin(user)

        try:
            package = CreditPackage.objects.get(id=packageId)
        except CreditPackage.DoesNotExist:
            raise Exception("Credit package not found")

        if input.name is not None:
            package.name = input.name
        if input.description is not None:
            package.description = input.description
        if input.priceUsd is not None:
            package.price_usd = input.priceUsd
        if input.bonusCredits is not None:
            package.bonus_credits = input.bonusCredits
        if input.isFeatured is not None:
            package.is_featured = input.isFeatured
        if input.isActive is not None:
            package.is_active = input.isActive
        if input.sortOrder is not None:
            package.sort_order = input.sortOrder
        if input.badgeLabel is not None:
            package.badge_label = input.badgeLabel

        package.save()
        return CreditPackageType.from_model(package)

    @strawberry.mutation
    def delete_credit_package(self, info: strawberry.types.Info, packageId: strawberry.ID) -> bool:
        """Delete a credit package (admin only)"""
        user = require_auth(info)
        require_admin(user)

        try:
            package = CreditPackage.objects.get(id=packageId)
            package.delete()
            return True
        except CreditPackage.DoesNotExist:
            raise Exception("Credit package not found")

    # Conversion Rate Admin Mutations
    @strawberry.mutation
    def create_conversion_rate(self, info: strawberry.types.Info, input: CreateConversionRateInput) -> CreditConversionRateType:
        """Create a new credit conversion rate (admin only)"""
        user = require_auth(info)
        require_admin(user)

        admin_account = getattr(user, 'admin_account', None)

        rate = CreditConversionRate.objects.create(
            credit_type=input.creditType or CreditType.FAN_CREDIT,
            credits_per_unit=input.creditsPerUnit,
            currency=input.currency or 'USD',
            monetary_value=input.monetaryValue,
            platform_fee_percent=input.platformFeePercent or 20.00,
            effective_from=input.effectiveFrom or timezone.now(),
            effective_until=input.effectiveUntil,
            created_by=admin_account
        )

        return CreditConversionRateType.from_model(rate)

    @strawberry.mutation
    def deactivate_conversion_rate(self, info: strawberry.types.Info, rateId: strawberry.ID) -> bool:
        """Deactivate a conversion rate (admin only)"""
        user = require_auth(info)
        require_admin(user)

        try:
            rate = CreditConversionRate.objects.get(id=rateId)
            rate.is_active = False
            rate.effective_until = timezone.now()
            rate.save()
            return True
        except CreditConversionRate.DoesNotExist:
            raise Exception("Conversion rate not found")
