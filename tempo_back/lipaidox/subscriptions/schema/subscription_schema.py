import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import Subscription, SubscriptionPayment

@strawberry.type
class SubscriptionType:
    id: strawberry.ID
    priceAtSignup: float
    currency: str
    billingCycle: str
    status: str
    currentPeriodStart: Optional[datetime]
    currentPeriodEnd: Optional[datetime]
    nextBillingDate: Optional[datetime]
    isTrial: bool
    cancelledAt: Optional[datetime]
    cancelAtPeriodEnd: bool
    startedAt: datetime

    @classmethod
    def from_model(cls, instance: Subscription):
        return cls(
            id=strawberry.ID(str(instance.id)),
            priceAtSignup=float(instance.price_at_signup),
            currency=instance.currency,
            billingCycle=instance.billing_cycle,
            status=instance.status,
            currentPeriodStart=instance.current_period_start,
            currentPeriodEnd=instance.current_period_end,
            nextBillingDate=instance.next_billing_date,
            isTrial=instance.is_trial,
            cancelledAt=instance.cancelled_at,
            cancelAtPeriodEnd=instance.cancel_at_period_end,
            startedAt=instance.started_at,
        )

@strawberry.type
class SubscriptionPaymentType:
    id: strawberry.ID
    paymentType: str
    paymentNumber: int
    amountPaid: float
    netAmount: float
    status: str
    periodStart: datetime
    periodEnd: datetime
    attemptedAt: datetime
    completedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: SubscriptionPayment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            paymentType=instance.payment_type,
            paymentNumber=instance.payment_number,
            amountPaid=float(instance.amount_paid),
            netAmount=float(instance.net_amount),
            status=instance.status,
            periodStart=instance.period_start,
            periodEnd=instance.period_end,
            attemptedAt=instance.attempted_at,
            completedAt=instance.completed_at,
        )
