import strawberry
from typing import Optional, List
from django.db.models import Q
from ..models import (
    CreditPackage, CreditConversionRate, CreditPurchase, CreditGift,
    CreatorCreditWallet, CreatorCreditLedger,
    FanCreditWallet, FanCreditLedger, FanCreditGiftSent,
    CreditType, CreditTransactionType
)
from ..schema.credits_schema import (
    CreditPackageType, CreditConversionRateType, CreditPurchaseType,
    CreatorCreditWalletType, CreatorCreditLedgerType,
    FanCreditWalletType, FanCreditLedgerType, FanCreditGiftSentType,
    EarningsCalculationType
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


@strawberry.type
class CreditsQuery:
    # Credit Package Queries (Public)
    @strawberry.field
    def credit_packages(
        self,
        info: strawberry.types.Info,
        creditType: Optional[str] = None,
        target: Optional[str] = None,
        isActive: Optional[bool] = True
    ) -> List[CreditPackageType]:
        """Get available credit packages"""
        queryset = CreditPackage.objects.all()

        if isActive is not None:
            queryset = queryset.filter(is_active=isActive)
        if creditType:
            queryset = queryset.filter(credit_type=creditType)
        if target:
            queryset = queryset.filter(target=target)

        return [CreditPackageType.from_model(pkg) for pkg in queryset.order_by('sort_order', 'price_usd')]

    @strawberry.field
    def credit_package_by_id(self, info: strawberry.types.Info, packageId: strawberry.ID) -> Optional[CreditPackageType]:
        """Get a specific credit package by ID"""
        try:
            package = CreditPackage.objects.get(id=packageId)
            return CreditPackageType.from_model(package)
        except CreditPackage.DoesNotExist:
            return None

    @strawberry.field
    def featured_packages(self, info: strawberry.types.Info, creditType: Optional[str] = None) -> List[CreditPackageType]:
        """Get featured credit packages"""
        queryset = CreditPackage.objects.filter(is_featured=True, is_active=True)
        if creditType:
            queryset = queryset.filter(credit_type=creditType)
        return [CreditPackageType.from_model(pkg) for pkg in queryset.order_by('sort_order')]

    # Conversion Rate Queries
    @strawberry.field
    def active_conversion_rates(
        self,
        info: strawberry.types.Info,
        creditType: Optional[str] = None
    ) -> List[CreditConversionRateType]:
        """Get active conversion rates"""
        from django.utils import timezone
        queryset = CreditConversionRate.objects.filter(
            is_active=True,
            effective_from__lte=timezone.now()
        ).filter(
            Q(effective_until__isnull=True) | Q(effective_until__gt=timezone.now())
        )

        if creditType:
            queryset = queryset.filter(credit_type=creditType)

        return [CreditConversionRateType.from_model(rate) for rate in queryset]

    @strawberry.field
    def calculate_gift_earnings(
        self,
        info: strawberry.types.Info,
        creditsAmount: int
    ) -> Optional[EarningsCalculationType]:
        """Calculate creator earnings for a given credit amount"""
        from django.utils import timezone
        try:
            rate = CreditConversionRate.objects.filter(
                credit_type=CreditType.FAN_CREDIT,
                is_active=True,
                effective_from__lte=timezone.now()
            ).filter(
                Q(effective_until__isnull=True) | Q(effective_until__gt=timezone.now())
            ).first()

            if not rate:
                return None

            earnings = rate.calculate_earnings(creditsAmount)
            return EarningsCalculationType(
                totalValue=earnings['total_value'],
                platformFee=earnings['platform_fee'],
                creatorEarnings=earnings['creator_earnings']
            )
        except Exception:
            return None

    # Creator Credit Queries
    @strawberry.field
    def my_creator_credit_wallet(self, info: strawberry.types.Info) -> Optional[CreatorCreditWalletType]:
        """Get current creator's credit wallet"""
        user = require_auth(info)
        require_creator(user)

        try:
            from lipaidox.creator_profile.models import CreatorProfile
            profile = CreatorProfile.objects.get(user=user)
            wallet, created = CreatorCreditWallet.objects.get_or_create(
                creator=profile,
                defaults={'tenant': user.tenant}
            )
            return CreatorCreditWalletType.from_model(wallet)
        except Exception:
            return None

    @strawberry.field
    def my_creator_credit_ledger(
        self,
        info: strawberry.types.Info,
        limit: int = 50,
        transactionType: Optional[str] = None
    ) -> List[CreatorCreditLedgerType]:
        """Get current creator's credit transaction history"""
        user = require_auth(info)
        require_creator(user)

        try:
            from lipaidox.creator_profile.models import CreatorProfile
            profile = CreatorProfile.objects.get(user=user)
            queryset = CreatorCreditLedger.objects.filter(creator=profile)

            if transactionType:
                queryset = queryset.filter(transaction_type=transactionType)

            return [CreatorCreditLedgerType.from_model(entry) for entry in queryset.order_by('-created_at')[:limit]]
        except Exception:
            return []

    # Fan Credit Queries
    @strawberry.field
    def my_fan_credit_wallet(self, info: strawberry.types.Info) -> Optional[FanCreditWalletType]:
        """Get current fan's credit wallet"""
        user = require_auth(info)

        wallet, created = FanCreditWallet.objects.get_or_create(
            fan=user,
            defaults={'tenant': user.tenant}
        )
        return FanCreditWalletType.from_model(wallet)

    @strawberry.field
    def my_fan_credit_ledger(
        self,
        info: strawberry.types.Info,
        limit: int = 50,
        transactionType: Optional[str] = None
    ) -> List[FanCreditLedgerType]:
        """Get current fan's credit transaction history"""
        user = require_auth(info)

        wallet, created = FanCreditWallet.objects.get_or_create(
            fan=user,
            defaults={'tenant': user.tenant}
        )

        queryset = FanCreditLedger.objects.filter(wallet=wallet)
        if transactionType:
            queryset = queryset.filter(transaction_type=transactionType)

        return [FanCreditLedgerType.from_model(entry) for entry in queryset.order_by('-created_at')[:limit]]

    @strawberry.field
    def my_gifts_sent(
        self,
        info: strawberry.types.Info,
        limit: int = 50
    ) -> List[FanCreditGiftSentType]:
        """Get gifts sent by current user"""
        user = require_auth(info)

        gifts = FanCreditGiftSent.objects.filter(fan=user).order_by('-sent_at')[:limit]
        return [FanCreditGiftSentType.from_model(gift) for gift in gifts]

    # Purchase History Queries
    @strawberry.field
    def my_credit_purchases(
        self,
        info: strawberry.types.Info,
        creditType: Optional[str] = None,
        limit: int = 50
    ) -> List[CreditPurchaseType]:
        """Get current user's credit purchase history"""
        user = require_auth(info)

        queryset = CreditPurchase.objects.filter(user=user)
        if creditType:
            queryset = queryset.filter(credit_type=creditType)

        return [CreditPurchaseType.from_model(purchase) for purchase in queryset.order_by('-purchased_at')[:limit]]

    # Admin Queries
    @strawberry.field
    def all_credit_purchases(
        self,
        info: strawberry.types.Info,
        creditType: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[CreditPurchaseType]:
        """Get all credit purchases (admin only)"""
        user = require_auth(info)
        require_admin(user)

        queryset = CreditPurchase.objects.all()
        if creditType:
            queryset = queryset.filter(credit_type=creditType)
        if status:
            queryset = queryset.filter(status=status)

        return [CreditPurchaseType.from_model(purchase) for purchase in queryset.order_by('-purchased_at')[:limit]]

    @strawberry.field
    def all_credit_gifts(
        self,
        info: strawberry.types.Info,
        creditType: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[CreditPurchaseType]:
        """Get all admin gifted credits (admin only)"""
        user = require_auth(info)
        require_admin(user)

        queryset = CreditGift.objects.all()
        if creditType:
            queryset = queryset.filter(credit_type=creditType)
        if status:
            queryset = queryset.filter(status=status)

        return [CreditGiftType.from_model(gift) for gift in queryset.order_by('-gifted_at')[:limit]]

    @strawberry.field
    def creator_credit_wallet_by_id(
        self,
        info: strawberry.types.Info,
        creatorId: strawberry.ID
    ) -> Optional[CreatorCreditWalletType]:
        """Get a creator's credit wallet by ID (admin only)"""
        user = require_auth(info)
        require_admin(user)

        try:
            wallet = CreatorCreditWallet.objects.get(creator_id=creatorId)
            return CreatorCreditWalletType.from_model(wallet)
        except CreatorCreditWallet.DoesNotExist:
            return None

    @strawberry.field
    def fan_credit_wallet_by_id(
        self,
        info: strawberry.types.Info,
        fanId: strawberry.ID
    ) -> Optional[FanCreditWalletType]:
        """Get a fan's credit wallet by ID (admin only)"""
        user = require_auth(info)
        require_admin(user)

        try:
            wallet = FanCreditWallet.objects.get(fan_id=fanId)
            return FanCreditWalletType.from_model(wallet)
        except FanCreditWallet.DoesNotExist:
            return None
