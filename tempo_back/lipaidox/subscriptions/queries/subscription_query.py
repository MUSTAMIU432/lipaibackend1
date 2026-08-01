import strawberry
from typing import Optional, List
from datetime import datetime
from ..schema.subscription_schema import SubscriptionType, SubscriptionPaymentType
from lipaidox.auth.permissions import require_any_role, require_creator

@strawberry.type
class SubscriptionQuery:
    @strawberry.field
    @require_any_role("fan", "creator", "admin")
    def my_subscriptions(self, info) -> List[SubscriptionType]:
        from ..models import Subscription
        user = info.context.request.user
        # Role validation handled by @require_any_role decorator
        return [SubscriptionType.from_model(s) for s in Subscription.objects.filter(fan=user)]

    @strawberry.field
    @require_creator
    def my_subscribers(self, info) -> List[SubscriptionType]:
        from ..models import Subscription
        from lipaidox.creator_profile.models import CreatorProfile
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        try:
            profile = CreatorProfile.objects.get(user=user)
            return [SubscriptionType.from_model(s) for s in Subscription.objects.filter(creator=profile)]
        except CreatorProfile.DoesNotExist:
            return []

    @strawberry.field
    def is_subscribed_to_creator(self, info, creator_id: strawberry.ID) -> bool:
        from ..models import Subscription, SubscriptionStatus
        user = info.context.request.user
        if not user.is_authenticated:
            return False
        return Subscription.objects.filter(
            fan=user, creator_id=creator_id, status=SubscriptionStatus.ACTIVE
        ).exists()
