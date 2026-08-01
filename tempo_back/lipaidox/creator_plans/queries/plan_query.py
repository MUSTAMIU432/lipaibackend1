import strawberry
from typing import List, Optional
from ..models import CreatorPlan, CreatorPlanSubscription, CreatorPlanPayment
from ..schema.plan_schema import CreatorPlanType, CreatorPlanSubscriptionType, CreatorPlanPaymentType
from lipaidox.creator_profile.models import CreatorProfile

@strawberry.type
class CreatorPlanQuery:
    @strawberry.field
    def available_plans(self) -> List[CreatorPlanType]:
        return [CreatorPlanType.from_model(p) for p in CreatorPlan.objects.filter(is_active=True)]

    @strawberry.field
    def my_plan_subscription(self, info) -> Optional[CreatorPlanSubscriptionType]:
        user = info.context.request.user
        if not user.is_authenticated: return None
        try:
            profile = CreatorProfile.objects.get(user=user)
            sub = CreatorPlanSubscription.objects.get(creator=profile)
            return CreatorPlanSubscriptionType.from_model(sub)
        except (CreatorProfile.DoesNotExist, CreatorPlanSubscription.DoesNotExist):
            return None

    @strawberry.field
    def my_plan_payments(self, info) -> List[CreatorPlanPaymentType]:
        user = info.context.request.user
        if not user.is_authenticated: return []
        try:
            profile = CreatorProfile.objects.get(user=user)
            payments = CreatorPlanPayment.objects.filter(creator=profile).order_by('-attempted_at')
            return [CreatorPlanPaymentType.from_model(p) for p in payments]
        except CreatorProfile.DoesNotExist:
            return []
