"""
One-to-one notification events: a like, a comment, a new follower, a follow
request and its answer. (A creator's new post fans out to many people and has
its own module, ``content_notifications``.)

``notify_user`` writes the in-app row straight away, then hands the device push
to a background task so the request that caused it (a like tap, a follow) never
waits on Firebase. Like the fan-out it is best-effort: it logs and returns None
rather than ever breaking the mutation that called it.
"""
import logging

logger = logging.getLogger(__name__)

# Notification types that carry action buttons, and the button set (app-side
# category id — see CATEGORIES in the app's src/lib/push-notifications.ts).
_CATEGORY_BY_TYPE = {
    "new_follow_request": "follow_request",
    "new_content_posted": "post",
    "new_like": "post",
    "new_comment": "post",
}


def notify_user(recipient, *, title, body, notification_type, sender=None,
                entity_type=None, entity_id=None, action_url=None, action_text=None,
                metadata=None, dedupe=True):
    """Create one notification for ``recipient`` and queue its push. Returns the row or None."""
    try:
        if recipient is None or (sender is not None and sender.pk == recipient.pk):
            return None

        from lipaidox.notifications.models.notification import Notification
        from lipaidox.notifications.models.notification_preferences import NotificationPreference

        prefs = NotificationPreference.get_or_create_for_user(recipient)
        if not prefs.is_enabled_for_type(notification_type):
            return None

        if dedupe and sender is not None:
            # Like → unlike → like must not stack three identical rows.
            if Notification.objects.filter(
                user=recipient, sender=sender, notification_type=notification_type,
                entity_type=entity_type, entity_id=entity_id, is_read=False,
            ).exists():
                return None

        notification = Notification.create_notification(
            recipient=recipient, title=title, body=body, notification_type=notification_type,
            sender=sender, entity_type=entity_type, entity_id=entity_id,
            action_url=action_url, action_text=action_text, metadata=metadata or {},
        )

        from lipaidox.notifications.tasks import send_notification_push_task
        from lipaidox.tasking import enqueue_on_commit

        enqueue_on_commit(send_notification_push_task, str(notification.pk))
        return notification
    except Exception as exc:
        logger.warning("notify_user(%s) failed: %s", notification_type, exc)
        return None


def deliver_push(notification):
    """Push one stored notification to the recipient's devices. Returns the number accepted."""
    from lipaidox.notifications.models.notification_preferences import NotificationPreference
    from lipaidox.notifications.services.push import active_tokens_for_users, send_push

    recipient = notification.user
    prefs = NotificationPreference.get_or_create_for_user(recipient)
    if not prefs.push_enabled or prefs.is_quiet_hours_active():
        return 0
    tokens = active_tokens_for_users([recipient])
    if not tokens:
        return 0

    ntype = str(notification.notification_type)
    data = {"type": ntype}
    if notification.entity_id:
        data["entityId"] = str(notification.entity_id)
    if notification.action_url:
        data["url"] = notification.action_url
    if notification.sender_id:
        data["senderId"] = str(notification.sender_id)
    return send_push(
        tokens, title=notification.title, body=notification.body, data=data,
        category=_CATEGORY_BY_TYPE.get(ntype),
    )


# ── Event helpers: one per place the product emits something ─────────────────

def _name(user):
    """Same naming the in-app list uses for a sender: full name, else username."""
    return ((user.get_full_name() or "").strip() or user.username or "Someone")


def _profile_url(user):
    username = getattr(getattr(user, "profile", None), "username", None)
    return f"/profile/{username or user.id}"


def notify_like(content, liker):
    owner = getattr(content.creator, "user", None)
    return notify_user(
        owner, title="New like on your post", body=f"{_name(liker)} liked your post ❤️",
        notification_type="new_like", sender=liker, entity_type="content",
        entity_id=str(content.id), action_url=f"/post/{content.id}", action_text="View post",
    )


def notify_comment(content, comment, author):
    text = (comment.body or "").strip()
    if len(text) > 120:
        text = text[:117] + "…"
    owner = getattr(content.creator, "user", None)
    notification = notify_user(
        owner, title="New comment on your post", body=f"{_name(author)} commented: “{text}”",
        notification_type="new_comment", sender=author, entity_type="content",
        entity_id=str(content.id), action_url=f"/post/{content.id}", action_text="View post",
        dedupe=False,
    )
    # A reply also tells the person being replied to (unless that is the post's owner, told above).
    parent = getattr(comment, "parent", None)
    if parent is not None and parent.author_id not in (author.pk, getattr(owner, "pk", None)):
        notify_user(
            parent.author, title="New reply to your comment", body=f"{_name(author)} replied: “{text}”",
            notification_type="new_comment", sender=author, entity_type="content",
            entity_id=str(content.id), action_url=f"/post/{content.id}", action_text="View post",
            dedupe=False,
        )
    return notification


def notify_follow(follower, target):
    return notify_user(
        target, title="New follower", body=f"{_name(follower)} started following you",
        notification_type="new_follower", sender=follower, entity_type="user",
        entity_id=str(follower.id), action_url=_profile_url(follower),
    )


def notify_follow_request(requester, target):
    return notify_user(
        target, title="Follow request", body=f"{_name(requester)} sent you a follow request.",
        notification_type="new_follow_request", sender=requester, entity_type="user",
        entity_id=str(requester.id), action_url="/notifications", action_text="Review",
    )


def notify_follow_request_accepted(target, requester):
    return notify_user(
        requester, title="Follow request accepted", body=f"{_name(target)} accepted your follow request.",
        notification_type="follow_request_accepted", sender=target, entity_type="user",
        entity_id=str(target.id),
        action_url=_profile_url(target),
    )
