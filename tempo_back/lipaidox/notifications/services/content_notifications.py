"""
Fan-out: notify a creator's audience when they post (YouTube/Instagram style).

`notify_new_content_posted(content)` is the single entry point. It is:

  * idempotent  — guarded by `content.followers_notified`, so editing or
    re-publishing an already-announced post never re-blasts the audience;
  * status-gated — only fires for `published` content;
  * preference-aware — skips users who turned off `notify_new_content_posted`;
  * best-effort — a delivery failure is logged, never raised, so it can't break
    the publish mutation that called it.

The audience is the union of the creator's followers, active paid subscribers,
and active free members. Each recipient gets one in-app `Notification` row (via
`bulk_create_notifications`) and, if they have a registered device, an Expo push.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _audience_users(creator):
    """Return the set of distinct recipient Users for a creator's new post."""
    creator_user = getattr(creator, "user", None)
    users = {}

    # Followers (creator_profile.Follow: follower -> followed user).
    try:
        from lipaidox.creator_profile.models.follow import Follow
        for f in Follow.objects.filter(followed=creator_user).select_related("follower"):
            if f.follower_id:
                users[f.follower_id] = f.follower
    except Exception as exc:
        logger.warning("new-content fan-out: follower lookup failed: %s", exc)

    # Active paid subscribers (subscriptions.Subscription: fan -> creator).
    try:
        from lipaidox.subscriptions.models.subscription import Subscription
        subs = Subscription.objects.filter(creator=creator, status="active").select_related("fan")
        now = timezone.now()
        for s in subs:
            end = getattr(s, "current_period_end", None)
            if end is None or end > now:
                if s.fan_id:
                    users[s.fan_id] = s.fan
    except Exception as exc:
        logger.warning("new-content fan-out: subscriber lookup failed: %s", exc)

    # Active free members (creator_profile.MembershipSubscription: subscriber -> target).
    try:
        from lipaidox.creator_profile.models.membership import (
            MembershipSubscription, MembershipStatus,
        )
        members = MembershipSubscription.objects.filter(
            target=creator, status=MembershipStatus.ACTIVE,
        ).select_related("subscriber")
        for m in members:
            if m.subscriber_id:
                users[m.subscriber_id] = m.subscriber
    except Exception as exc:
        logger.warning("new-content fan-out: member lookup failed: %s", exc)

    # Never notify the creator about their own post.
    if creator_user is not None:
        users.pop(creator_user.id, None)

    return list(users.values())


def _preference_allows(user):
    """Respect the user's `notify_new_content_posted` toggle (default on)."""
    try:
        from lipaidox.notifications.models.notification_preferences import NotificationPreference
        from lipaidox.notifications.models.enums import NotificationType
        prefs = NotificationPreference.get_or_create_for_user(user)
        return prefs.is_enabled_for_type(NotificationType.NEW_CONTENT_POSTED)
    except Exception:
        return True


def notify_new_content_posted(content):
    """Announce a newly-published post to its creator's audience. Idempotent."""
    try:
        if content is None or content.status != "published" or getattr(content, "followers_notified", False):
            return 0

        from lipaidox.notifications.models.notification import Notification
        from lipaidox.notifications.models.enums import NotificationType, NotificationPriority

        creator = content.creator
        creator_name = getattr(creator, "display_name", None) or getattr(creator, "username", "A creator")

        recipients = [u for u in _audience_users(creator) if _preference_allows(u)]

        # Mark notified up-front so a concurrent publish can't double-send, even
        # if there are no recipients yet.
        content.followers_notified = True
        content.save(update_fields=["followers_notified"])

        if not recipients:
            return 0

        title = f"{creator_name} posted something new"
        body = content.title or "New content is available"
        action_url = f"/post/{content.id}"

        Notification.bulk_create_notifications(
            recipients,
            title=title,
            body=body,
            notification_type=NotificationType.NEW_CONTENT_POSTED,
            priority=NotificationPriority.NORMAL,
            action_url=action_url,
            action_text="View post",
            # entity_* lets the mobile client deep-link the tap straight to the post.
            entity_type="content",
            entity_id=str(content.id),
            metadata={"contentId": str(content.id), "creatorName": creator_name},
        )

        # Device push (best-effort).
        try:
            from lipaidox.notifications.services.push import send_expo_push, active_tokens_for_users
            tokens = active_tokens_for_users(recipients)
            if tokens:
                send_expo_push(
                    tokens,
                    title=title,
                    body=body,
                    data={"type": "new_content_posted", "entityId": str(content.id), "url": action_url},
                )
        except Exception as exc:
            logger.warning("new-content push delivery failed: %s", exc)

        return len(recipients)
    except Exception as exc:
        logger.error("notify_new_content_posted failed: %s", exc)
        return 0
