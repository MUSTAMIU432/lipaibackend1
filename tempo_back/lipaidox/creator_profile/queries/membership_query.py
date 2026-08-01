import strawberry
from ..models import MembershipSubscription, MembershipStatus
from ..schema.membership_schema import (
    SubscriptionStatusResult,
    SubscriberUserType,
    SubscriberListType,
    MembershipItemType,
    MembershipListType,
    CreatorSummaryType,
)
from ..services.social_service import (
    require_user,
    get_target_profile,
    active_subscriber_count,
    subscriber_user_fields,
    creator_summary_fields,
)


@strawberry.type
class MembershipQuery:
    @strawberry.field
    def subscription_status(self, info, target_user_id: strawberry.ID) -> SubscriptionStatusResult:
        profile = get_target_profile(target_user_id)
        count = active_subscriber_count(profile)
        user = info.context.request.user
        if not getattr(user, "is_authenticated", False):
            return SubscriptionStatusResult(isSubscribed=False, subscriberCount=count)
        sub = MembershipSubscription.objects.filter(
            subscriber=user, target=profile, status=MembershipStatus.ACTIVE
        ).first()
        return SubscriptionStatusResult(
            isSubscribed=sub is not None,
            subscriberCount=count,
            status=sub.status if sub else None,
            notificationPreference=sub.notification_preference if sub else None,
        )

    @strawberry.field
    def my_subscriptions(self, info, offset: int = 0, limit: int = 20) -> MembershipListType:
        user = require_user(info)
        qs = (
            MembershipSubscription.objects.filter(subscriber=user, status=MembershipStatus.ACTIVE)
            .select_related("target", "target__user")
            .order_by("-created_at")
        )
        total = qs.count()
        items = [
            MembershipItemType(
                id=strawberry.ID(str(m.id)),
                status=m.status,
                notificationPreference=m.notification_preference,
                createdAt=m.created_at,
                creator=CreatorSummaryType(**creator_summary_fields(m.target)),
            )
            for m in qs[offset:offset + limit]
        ]
        return MembershipListType(items=items, totalCount=total)

    @strawberry.field
    def subscribers(self, info, target_user_id: strawberry.ID, offset: int = 0, limit: int = 20) -> SubscriberListType:
        profile = get_target_profile(target_user_id)
        qs = (
            MembershipSubscription.objects.filter(target=profile, status=MembershipStatus.ACTIVE)
            .select_related("subscriber", "subscriber__profile")
            .order_by("-created_at")
        )
        total = qs.count()
        users = [
            SubscriberUserType(**subscriber_user_fields(m.subscriber))
            for m in qs[offset:offset + limit]
        ]
        return SubscriberListType(users=users, totalCount=total)
