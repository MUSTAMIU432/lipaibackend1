import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..models import (
    CreditPackage, CreditConversionRate, CreditPurchase, CreditGift,
    CreatorCreditWallet, CreatorCreditLedger,
    FanCreditWallet, FanCreditLedger, FanCreditGiftSent,
    CreditType, CreditTransactionType, CreditTransactionStatus,
    CreditGiftStatus, CreditPackageTarget, GiftAnimationType
)


# Credit Package Types
@strawberry.type
class CreditPackageType:
    id: strawberry.ID
    name: str
    description: Optional[str]
    creditType: str
    target: str
    creditAmount: int
    priceUsd: Decimal
    bonusCredits: int
    totalCredits: int
    durationMinutes: Optional[int]
    isFeatured: bool
    isActive: bool
    sortOrder: int
    badgeLabel: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: CreditPackage):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            description=instance.description,
            creditType=instance.credit_type,
            target=instance.target,
            creditAmount=instance.credit_amount,
            priceUsd=instance.price_usd,
            bonusCredits=instance.bonus_credits,
            totalCredits=instance.total_credits,
            durationMinutes=instance.duration_minutes,
            isFeatured=instance.is_featured,
            isActive=instance.is_active,
            sortOrder=instance.sort_order,
            badgeLabel=instance.badge_label,
            createdAt=instance.created_at,
        )


@strawberry.type
class CreditConversionRateType:
    id: strawberry.ID
    creditType: str
    creditsPerUnit: int
    currency: str
    monetaryValue: Decimal
    platformFeePercent: Decimal
    creatorReceives: Decimal
    isActive: bool
    effectiveFrom: datetime
    effectiveUntil: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: CreditConversionRate):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creditType=instance.credit_type,
            creditsPerUnit=instance.credits_per_unit,
            currency=instance.currency,
            monetaryValue=instance.monetary_value,
            platformFeePercent=instance.platform_fee_percent,
            creatorReceives=instance.creator_receives,
            isActive=instance.is_active,
            effectiveFrom=instance.effective_from,
            effectiveUntil=instance.effective_until,
            createdAt=instance.created_at,
        )


@strawberry.type
class CreditPurchaseType:
    id: strawberry.ID
    userId: strawberry.ID
    creditType: str
    packageId: strawberry.ID
    creditsPurchased: int
    bonusCredits: int
    totalCredits: int
    amountPaid: Decimal
    currency: str
    status: str
    paymentMethodId: Optional[strawberry.ID]
    transactionReference: Optional[str]
    gatewayReference: Optional[str]
    purchasedAt: datetime
    completedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: CreditPurchase):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            creditType=instance.credit_type,
            packageId=strawberry.ID(str(instance.package_id)),
            creditsPurchased=instance.credits_purchased,
            bonusCredits=instance.bonus_credits,
            totalCredits=instance.total_credits,
            amountPaid=instance.amount_paid,
            currency=instance.currency,
            status=instance.status,
            paymentMethodId=strawberry.ID(str(instance.payment_method_id)) if instance.payment_method else None,
            transactionReference=instance.transaction_reference,
            gatewayReference=instance.gateway_reference,
            purchasedAt=instance.purchased_at,
            completedAt=instance.completed_at,
        )


@strawberry.type
class CreditGiftType:
    id: strawberry.ID
    giftedToUserId: strawberry.ID
    giftedByAdminId: strawberry.ID
    creditType: str
    creditsAmount: int
    reason: str
    internalNote: Optional[str]
    status: str
    expiresAt: Optional[datetime]
    giftedAt: datetime
    deliveredAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: CreditGift):
        return cls(
            id=strawberry.ID(str(instance.id)),
            giftedToUserId=strawberry.ID(str(instance.gifted_to_user_id)),
            giftedByAdminId=strawberry.ID(str(instance.gifted_by_admin_id)),
            creditType=instance.credit_type,
            creditsAmount=instance.credits_amount,
            reason=instance.reason,
            internalNote=instance.internal_note,
            status=instance.status,
            expiresAt=instance.expires_at,
            giftedAt=instance.gifted_at,
            deliveredAt=instance.delivered_at,
        )


@strawberry.type
class CreatorCreditWalletType:
    id: strawberry.ID
    creatorId: strawberry.ID
    purchasedCredits: int
    freeMonthlyCredits: int
    giftedCredits: int
    totalAvailableCredits: int
    totalCreditsUsed: int
    totalCreditsPurchased: int
    totalCreditsGifted: int
    monthlyCreditsAllocated: int
    monthlyResetAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorCreditWallet):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            purchasedCredits=instance.purchased_credits,
            freeMonthlyCredits=instance.free_monthly_credits,
            giftedCredits=instance.gifted_credits,
            totalAvailableCredits=instance.total_available_credits,
            totalCreditsUsed=instance.total_credits_used,
            totalCreditsPurchased=instance.total_credits_purchased,
            totalCreditsGifted=instance.total_credits_gifted,
            monthlyCreditsAllocated=instance.monthly_credits_allocated,
            monthlyResetAt=instance.monthly_reset_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class CreatorCreditLedgerType:
    id: strawberry.ID
    creatorId: strawberry.ID
    walletId: strawberry.ID
    transactionType: str
    creditsDelta: int
    creditsBefore: int
    creditsAfter: int
    purchaseId: Optional[strawberry.ID]
    giftId: Optional[strawberry.ID]
    liveStreamId: Optional[strawberry.ID]
    expiresAt: Optional[datetime]
    isExpired: bool
    description: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorCreditLedger):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            walletId=strawberry.ID(str(instance.wallet_id)),
            transactionType=instance.transaction_type,
            creditsDelta=instance.credits_delta,
            creditsBefore=instance.credits_before,
            creditsAfter=instance.credits_after,
            purchaseId=strawberry.ID(str(instance.purchase_id)) if instance.purchase else None,
            giftId=strawberry.ID(str(instance.gift_id)) if instance.gift else None,
            liveStreamId=str(instance.live_stream_id) if instance.live_stream_id else None,
            expiresAt=instance.expires_at,
            isExpired=instance.is_expired,
            description=instance.description,
            createdAt=instance.created_at,
        )


@strawberry.type
class FanCreditWalletType:
    id: strawberry.ID
    fanId: strawberry.ID
    purchasedCredits: int
    giftedCredits: int
    totalAvailableCredits: int
    totalCreditsPurchased: int
    totalCreditsGiftedByAdmin: int
    totalCreditsSent: int
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: FanCreditWallet):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            purchasedCredits=instance.purchased_credits,
            giftedCredits=instance.gifted_credits,
            totalAvailableCredits=instance.total_available_credits,
            totalCreditsPurchased=instance.total_credits_purchased,
            totalCreditsGiftedByAdmin=instance.total_credits_gifted_by_admin,
            totalCreditsSent=instance.total_credits_sent,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class FanCreditLedgerType:
    id: strawberry.ID
    fanId: strawberry.ID
    walletId: strawberry.ID
    transactionType: str
    creditsDelta: int
    creditsBefore: int
    creditsAfter: int
    purchaseId: Optional[strawberry.ID]
    giftId: Optional[strawberry.ID]
    giftSentId: Optional[strawberry.ID]
    description: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: FanCreditLedger):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            walletId=strawberry.ID(str(instance.wallet_id)),
            transactionType=instance.transaction_type,
            creditsDelta=instance.credits_delta,
            creditsBefore=instance.credits_before,
            creditsAfter=instance.credits_after,
            purchaseId=strawberry.ID(str(instance.purchase_id)) if instance.purchase else None,
            giftId=strawberry.ID(str(instance.gift_id)) if instance.gift else None,
            giftSentId=strawberry.ID(str(instance.gift_sent_id)) if instance.gift_sent else None,
            description=instance.description,
            createdAt=instance.created_at,
        )


@strawberry.type
class FanCreditGiftSentType:
    id: strawberry.ID
    fanId: strawberry.ID
    creatorId: strawberry.ID
    liveStreamId: strawberry.ID
    creditsSent: int
    animationType: str
    message: Optional[str]
    isAnonymous: bool
    monetaryValue: Optional[Decimal]
    platformFee: Optional[Decimal]
    creatorEarnings: Optional[Decimal]
    status: str
    deliveredAt: Optional[datetime]
    creatorWalletCredited: bool
    sentAt: datetime

    @classmethod
    def from_model(cls, instance: FanCreditGiftSent):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            liveStreamId=str(instance.live_stream_id),
            creditsSent=instance.credits_sent,
            animationType=instance.animation_type,
            message=instance.message,
            isAnonymous=instance.is_anonymous,
            monetaryValue=instance.monetary_value,
            platformFee=instance.platform_fee,
            creatorEarnings=instance.creator_earnings,
            status=instance.status,
            deliveredAt=instance.delivered_at,
            creatorWalletCredited=instance.creator_wallet_credited,
            sentAt=instance.sent_at,
        )


# Earnings Calculation Type
@strawberry.type
class EarningsCalculationType:
    totalValue: Decimal
    platformFee: Decimal
    creatorEarnings: Decimal


# Input Types
@strawberry.input
class PurchaseCreditsInput:
    packageId: strawberry.ID


@strawberry.input
class GiftCreditsInput:
    userId: strawberry.ID
    creditType: str
    creditsAmount: int
    reason: str
    internalNote: Optional[str] = None
    expiresAt: Optional[datetime] = None


@strawberry.input
class SendGiftInput:
    creatorId: strawberry.ID
    liveStreamId: strawberry.ID
    creditsAmount: int
    animationType: Optional[str] = 'heart'
    message: Optional[str] = None
    isAnonymous: bool = False


@strawberry.input
class UseCreatorCreditsInput:
    liveStreamId: strawberry.ID
    creditsAmount: int = 1


@strawberry.input
class CreateCreditPackageInput:
    name: str
    description: Optional[str] = None
    creditType: str
    target: Optional[str] = 'both'
    creditAmount: int
    priceUsd: Decimal
    bonusCredits: Optional[int] = 0
    durationMinutes: Optional[int] = None
    isFeatured: bool = False
    isActive: bool = True
    sortOrder: Optional[int] = 0
    badgeLabel: Optional[str] = None


@strawberry.input
class UpdateCreditPackageInput:
    name: Optional[str] = None
    description: Optional[str] = None
    priceUsd: Optional[Decimal] = None
    bonusCredits: Optional[int] = None
    isFeatured: Optional[bool] = None
    isActive: Optional[bool] = None
    sortOrder: Optional[int] = None
    badgeLabel: Optional[str] = None


@strawberry.input
class CreateConversionRateInput:
    creditType: Optional[str] = 'fan_credit'
    creditsPerUnit: int
    currency: Optional[str] = 'USD'
    monetaryValue: Decimal
    platformFeePercent: Optional[Decimal] = 20.00
    effectiveFrom: Optional[datetime] = None
    effectiveUntil: Optional[datetime] = None
