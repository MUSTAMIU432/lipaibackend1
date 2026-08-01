"""Shared helpers for direct-message GraphQL resolvers."""


def require_auth(info):
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def get_user(info):
    user = info.context.request.user
    return user if user.is_authenticated else None


def side_of(conversation, user):
    """Return 'fan' or 'creator' for the given user, or None if not a participant."""
    if user is None:
        return None
    if conversation.fan_id == user.id:
        return 'fan'
    if conversation.creator_id == user.id:
        return 'creator'
    return None


def other_party(conversation, user):
    """Return the other participant User of a conversation relative to `user`."""
    if user is not None and conversation.fan_id == user.id:
        return conversation.creator
    return conversation.fan


def creator_profile_of(user):
    """Return the user's CreatorProfile (FK target for creator-owned rows), or None.

    `QuickReply.creator` and other creator-owned models point at CreatorProfile,
    not User, so resolvers must translate the request user to their profile before
    filtering/creating — otherwise Django raises
    `Cannot query "<user>": Must be "CreatorProfile" instance.`
    """
    if user is None:
        return None
    try:
        return user.profile
    except Exception:
        return None


def display_name(user):
    if user is None:
        return "Unknown"
    full = (user.get_full_name() or "").strip()
    return full or user.username


def avatar_url(user):
    if user is None:
        return None
    try:
        profile = user.profile
    except Exception:
        return None
    return getattr(profile, "profile_photo_url", None)
