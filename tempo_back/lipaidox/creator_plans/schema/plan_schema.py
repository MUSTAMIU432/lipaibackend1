import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import CreatorPlanSubscription, CreatorPlanPayment, CreatorPlan
from ..services import annual_total

@strawberry.type
class CreatorPlanType:
    id: strawberry.ID
    tier: str
    name: str
    pricePerMonth: float
    description: Optional[str]
    canMonetize: bool
    monthlyFreeCredits: int
    unlimitedLiveSessions: int
    annualDiscountPercent: float
    annualPrice: float
    platformFeePercent: Optional[float]
    maxPremiumContentPerMonth: Optional[int]
    maxContentUploadsPerMonth: Optional[int]
    maxLiveCountries: Optional[int]
    maxSubscriptionTiers: int

    @classmethod
    def from_model(cls, instance: CreatorPlan):
        return cls(
            id=strawberry.ID(str(instance.id)),
            tier=instance.tier,
            name=instance.name,
            pricePerMonth=float(instance.price_per_month),
            description=instance.description,
            canMonetize=instance.can_monetize,
            monthlyFreeCredits=instance.monthly_free_credits,
            unlimitedLiveSessions=instance.unlimited_live_sessions,
            annualDiscountPercent=float(instance.annual_discount_percent),
            annualPrice=float(annual_total(instance)),
            platformFeePercent=(
                float(instance.platform_fee_percent) if instance.platform_fee_percent is not None else None
            ),
            maxPremiumContentPerMonth=instance.max_premium_content_per_month,
            maxContentUploadsPerMonth=instance.max_content_uploads_per_month,
            maxLiveCountries=instance.max_live_countries,
            maxSubscriptionTiers=instance.max_subscription_tiers,
        )

@strawberry.type
class CreatorPlanSubscriptionType:
    id: strawberry.ID
    planTier: str
    status: str
    currentPeriodEnd: Optional[datetime]
    availableCredits: int
    cancelAtPeriodEnd: bool

    @classmethod
    def from_model(cls, instance: CreatorPlanSubscription):
        return cls(
            id=strawberry.ID(str(instance.id)),
            planTier=instance.plan_tier,
            status=instance.status,
            currentPeriodEnd=instance.current_period_end,
            availableCredits=instance.available_credits,
            cancelAtPeriodEnd=instance.cancel_at_period_end,
        )

@strawberry.type
class CreatorPlanPaymentType:
    id: strawberry.ID
    paymentType: str
    amountPaid: float
    status: str
    attemptedAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorPlanPayment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            paymentType=instance.payment_type,
            amountPaid=float(instance.amount_paid),
            status=instance.status,
            attemptedAt=instance.attempted_at,
        )
