"""
Per-viewer content access decisions.

Single source of truth for "may this user see the full media of this content?"
Used by the GraphQL ContentType resolvers (viewerHasAccess / gated media fileUrl)
and by media signed-URL minting. Read-only — never mutates.
"""
from typing import Optional

from lipaidox.content.models.content import Content, ContentAccessType


def _is_authed(user) -> bool:
    return bool(user is not None and getattr(user, "is_authenticated", False))


def viewer_is_owner(user, content: Content) -> bool:
    if not _is_authed(user):
        return False
    return content.creator.user_id == user.id


def _viewer_subscribed(user, content: Content) -> bool:
    """Active subscription to the content's creator — free membership OR (Phase 4)
    paid subscription. Kept here so subscription-gated content resolves today."""
    try:
        from lipaidox.subscriptions.services import has_active_subscription
        return has_active_subscription(user, content.creator)
    except Exception:
        # Fallback before the unified helper exists: free membership only.
        try:
            from lipaidox.creator_profile.models.membership import (
                MembershipSubscription, MembershipStatus,
            )
            return MembershipSubscription.objects.filter(
                subscriber=user, target=content.creator, status=MembershipStatus.ACTIVE,
            ).exists()
        except Exception:
            return False


def viewer_has_access(user, content: Content) -> bool:
    """Whether `user` may view the full (ungated) media of `content`."""
    access_type = content.access_type

    if access_type == ContentAccessType.FREE:
        return True

    if not _is_authed(user):
        return False

    if content.creator.user_id == user.id:
        return True

    if access_type in (ContentAccessType.ONE_TIME, ContentAccessType.TIMED):
        from lipaidox.ppv.models import PPVPurchase
        try:
            return PPVPurchase.objects.get(fan=user, content=content).has_access
        except PPVPurchase.DoesNotExist:
            return False

    if access_type == ContentAccessType.SUBSCRIPTION:
        return _viewer_subscribed(user, content)

    return False


def viewer_purchase(user, content: Content):
    """Return the user's PPVPurchase for this content, or None."""
    if not _is_authed(user):
        return None
    from lipaidox.ppv.models import PPVPurchase
    try:
        return PPVPurchase.objects.get(fan=user, content=content)
    except PPVPurchase.DoesNotExist:
        return None
