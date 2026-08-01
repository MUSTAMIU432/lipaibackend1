import strawberry
from django.db import transaction, IntegrityError
from django.utils import timezone

from ..models import MembershipSubscription, MembershipStatus, NotificationPreference
from ..schema.membership_schema import (
    SubscribeFreePayload,
    UnsubscribePayload,
    UpdateNotificationPreferencePayload,
)
from ..services.social_service import require_user, get_target_profile, recalc_subscriber_count


_VALID_PREFS = {c[0] for c in NotificationPreference.choices}


@strawberry.type
class MembershipMutation:
    @strawberry.mutation
    def subscribe_free(self, info, target_user_id: strawberry.ID) -> SubscribeFreePayload:
        user = require_user(info)
        profile = get_target_profile(target_user_id)
        if str(profile.user_id) == str(user.id):
            raise Exception("You cannot subscribe to yourself")

        with transaction.atomic():
            try:
                sub, _ = MembershipSubscription.objects.get_or_create(
                    subscriber=user,
                    target=profile,
                    tenant=getattr(user, "tenant", None),
                    defaults={"status": MembershipStatus.ACTIVE},
                )
            except IntegrityError:
                sub = MembershipSubscription.objects.get(subscriber=user, target=profile)
            # Idempotent: re-activate a previously cancelled membership.
            if sub.status != MembershipStatus.ACTIVE:
                sub.status = MembershipStatus.ACTIVE
                sub.ended_at = None
                sub.save(update_fields=["status", "ended_at", "updated_at"])
            count = recalc_subscriber_count(profile)

        return SubscribeFreePayload(
            isSubscribed=True,
            status=MembershipStatus.ACTIVE,
            subscriberCount=count,
            notificationPreference=sub.notification_preference,
        )

    @strawberry.mutation
    def unsubscribe(self, info, target_user_id: strawberry.ID) -> UnsubscribePayload:
        user = require_user(info)
        profile = get_target_profile(target_user_id)
        with transaction.atomic():
            sub = MembershipSubscription.objects.filter(subscriber=user, target=profile).first()
            if sub and sub.status == MembershipStatus.ACTIVE:
                sub.status = MembershipStatus.CANCELLED
                sub.ended_at = timezone.now()
                sub.save(update_fields=["status", "ended_at", "updated_at"])
            count = recalc_subscriber_count(profile)
        return UnsubscribePayload(isSubscribed=False, subscriberCount=count)

    @strawberry.mutation
    def update_subscription_notification_preference(
        self, info, target_user_id: strawberry.ID, preference: str
    ) -> UpdateNotificationPreferencePayload:
        user = require_user(info)
        profile = get_target_profile(target_user_id)
        pref = (preference or "").lower()
        if pref not in _VALID_PREFS:
            raise Exception("Invalid notification preference")
        sub = MembershipSubscription.objects.filter(
            subscriber=user, target=profile, status=MembershipStatus.ACTIVE
        ).first()
        if sub is None:
            raise Exception("You are not subscribed to this creator")
        # NONE preference must NOT cancel the subscription — only mute notifications.
        sub.notification_preference = pref
        sub.save(update_fields=["notification_preference", "updated_at"])
        return UpdateNotificationPreferencePayload(isSubscribed=True, notificationPreference=pref)
