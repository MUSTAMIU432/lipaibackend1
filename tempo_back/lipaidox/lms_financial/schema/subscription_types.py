import strawberry
from datetime import datetime
from typing import Optional
from ..models.subscription import LmsSubscription
from .plan_types import LmsPlanNode

@strawberry.type
class LmsSubscriptionNode:
    id: strawberry.ID
    plan: LmsPlanNode
    status: str
    startDate: datetime
    endDate: Optional[datetime]
    stripeSubscriptionId: Optional[str]
    cancelAtPeriodEnd: bool

    @classmethod
    def from_model(cls, instance: LmsSubscription):
        return cls(
            id=strawberry.ID(str(instance.id)),
            plan=LmsPlanNode.from_model(instance.plan),
            status=instance.status,
            startDate=instance.start_date,
            endDate=instance.end_date,
            stripeSubscriptionId=instance.stripe_subscription_id,
            cancelAtPeriodEnd=instance.cancel_at_period_end,
        )
