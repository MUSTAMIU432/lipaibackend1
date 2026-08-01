import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import MonetizationSettings, MonetizationPriceHistory

@strawberry.type
class MonetizationSettingsType:
    id: strawberry.ID
    subscriptionEnabled: bool
    subscriptionPrice: Optional[float]
    subscriptionBillingCycle: str
    ppvEnabled: bool
    ppvPrice: Optional[float]
    tipsEnabled: bool
    tipMinAmount: float
    tipMaxAmount: float
    tipSuggestedAmounts: List[float]
    displayCurrency: str
    platformFeePercent: float

    @classmethod
    def from_model(cls, instance: MonetizationSettings):
        return cls(
            id=strawberry.ID(str(instance.id)),
            subscriptionEnabled=instance.subscription_enabled,
            subscriptionPrice=float(instance.subscription_price) if instance.subscription_price else None,
            subscriptionBillingCycle=instance.subscription_billing_cycle,
            ppvEnabled=instance.ppv_enabled,
            ppvPrice=float(instance.ppv_price) if instance.ppv_price else None,
            tipsEnabled=instance.tips_enabled,
            tipMinAmount=float(instance.tip_min_amount),
            tipMaxAmount=float(instance.tip_max_amount),
            tipSuggestedAmounts=[float(a) for a in instance.tip_suggested_amounts],
            displayCurrency=instance.display_currency,
            platformFeePercent=float(instance.platform_fee_percent),
        )

@strawberry.input
class MonetizationUpdateInput:
    subscriptionEnabled: Optional[bool] = None
    subscriptionPrice: Optional[float] = None
    subscriptionBillingCycle: Optional[str] = None
    ppvEnabled: Optional[bool] = None
    ppvPrice: Optional[float] = None
    tipsEnabled: Optional[bool] = None
    tipMinAmount: Optional[float] = None
    tipMaxAmount: Optional[float] = None
    displayCurrency: Optional[str] = None
