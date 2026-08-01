"""
Unified subscription access check.

`has_active_subscription(user, creator_profile)` is True when the user has EITHER
an active paid Subscription OR an active free MembershipSubscription to the creator.
Used by content access gating (access_type=subscription), live-stream join gating,
and subscription status queries.
"""
from django.utils import timezone


def has_active_subscription(user, creator_profile) -> bool:
    if user is None or not getattr(user, "is_authenticated", False) or creator_profile is None:
        return False

    # Paid subscription (subscriptions app).
    try:
        from lipaidox.subscriptions.models.subscription import Subscription
        active_paid = Subscription.objects.filter(
            fan=user, creator=creator_profile, status="active",
        )
        # Respect current period if the model tracks it.
        for sub in active_paid:
            end = getattr(sub, "current_period_end", None)
            if end is None or end > timezone.now():
                return True
    except Exception:
        pass

    # Free membership (creator_profile app).
    try:
        from lipaidox.creator_profile.models.membership import (
            MembershipSubscription, MembershipStatus,
        )
        return MembershipSubscription.objects.filter(
            subscriber=user, target=creator_profile, status=MembershipStatus.ACTIVE,
        ).exists()
    except Exception:
        return False
