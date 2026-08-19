import strawberry
from typing import Optional, List
from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone

from ..models import (
    Conversation, ConversationType, Message, MessageType,
    QuickReply, ScheduledMessage, MessageReaction, ConversationReport,
)
from ..schema.types import (
    DmConversationType, DmMessageType, DmQuickReplyType, DmScheduledMessageType,
    SendDmInput,
)
from ..schema.helpers import require_auth, side_of, other_party, creator_profile_of

_DISAPPEAR_SECONDS = {"1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000}


def _get_conversation(user, conversation_id):
    conv = Conversation.objects.filter(
        Q(id=conversation_id) & (Q(fan=user) | Q(creator=user))
    ).select_related("fan", "creator").first()
    if conv is None:
        raise Exception("Conversation not found")
    return conv


def _get_reactable_message(user, message_id):
    """A message the user may react to — i.e. one in a conversation they belong
    to. Without this membership check any authenticated user could react to any
    message by id."""
    msg = (
        Message.objects.filter(id=message_id)
        .filter(Q(conversation__fan=user) | Q(conversation__creator=user))
        .select_related("conversation")
        .first()
    )
    if msg is None:
        raise Exception("Message not found")
    return msg


def _compute_expiry(conv, disappear_after):
    mode = disappear_after or conv.disappearing_enabled or "off"
    if mode == "off":
        return "off", None
    if mode == "custom":
        ms = conv.disappearing_duration_ms or 0
        return mode, (timezone.now() + timedelta(milliseconds=ms)) if ms else None
    secs = _DISAPPEAR_SECONDS.get(mode)
    return mode, (timezone.now() + timedelta(seconds=secs)) if secs else None


@strawberry.type
class DmMutations:

    # ── Conversations ─────────────────────────────────────────────────────────

    @strawberry.mutation
    def start_dm_conversation(
        self, info, other_user_id: strawberry.ID, text: Optional[str] = None
    ) -> DmConversationType:
        user = require_auth(info)
        from lipaidox.auth.models import User
        other = User.objects.filter(id=other_user_id).first()
        if other is None:
            raise Exception("User not found")
        # canonical (fan, creator) ordering: current user as fan if their role isn't creator
        is_creator = getattr(user, "role", "") == "creator"
        fan, creator = (other, user) if is_creator else (user, other)
        conv = Conversation.objects.filter(
            (Q(fan=fan, creator=creator) | Q(fan=creator, creator=fan))
        ).first()
        if conv is None:
            conv = Conversation.objects.create(
                fan=fan, creator=creator,
                tenant=getattr(user, "tenant", None),
                conversation_type=ConversationType.FAN_TO_CREATOR,
            )
        if text:
            _create_message(conv, user, body=text)
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def mark_dm_conversation_read(
        self, info, conversation_id: strawberry.ID
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        side = side_of(conv, user)
        if side == 'fan':
            conv.fan_unread_count = 0
        else:
            conv.creator_unread_count = 0
        conv.save(update_fields=["fan_unread_count", "creator_unread_count"])
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def pin_dm_conversation(
        self, info, conversation_id: strawberry.ID, pinned: bool
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        if side_of(conv, user) == 'fan':
            conv.pinned_by_fan = pinned
        else:
            conv.pinned_by_creator = pinned
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def mute_dm_conversation(
        self, info, conversation_id: strawberry.ID, muted: bool
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        if side_of(conv, user) == 'fan':
            conv.muted_by_fan = muted
        else:
            conv.muted_by_creator = muted
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def hide_dm_conversation(
        self, info, conversation_id: strawberry.ID, hidden: bool
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        if side_of(conv, user) == 'fan':
            conv.hidden_by_fan = hidden
        else:
            conv.hidden_by_creator = hidden
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def clear_dm_conversation(
        self, info, conversation_id: strawberry.ID
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        now = timezone.now()
        if side_of(conv, user) == 'fan':
            conv.cleared_at_fan = now
        else:
            conv.cleared_at_creator = now
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def report_dm_conversation(
        self, info, conversation_id: strawberry.ID,
        category: str = "spam", reason: Optional[str] = None
    ) -> bool:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        ConversationReport.objects.create(
            conversation=conv, reporter=user,
            tenant=getattr(user, "tenant", None),
            category=category, reason=reason,
        )
        return True

    @strawberry.mutation
    def set_dm_disappearing(
        self, info, conversation_id: strawberry.ID,
        enabled: str, duration_ms: Optional[int] = None
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        conv.disappearing_enabled = enabled
        conv.disappearing_duration_ms = duration_ms
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def lock_dm_conversation(
        self, info, conversation_id: strawberry.ID,
        lock_type: str, lock_code: str, secret_name: Optional[str] = None
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        conv.is_locked = True
        conv.lock_type = lock_type
        conv.lock_code = lock_code
        conv.secret_name = secret_name
        conv.save()
        return DmConversationType.from_model(conv, user)

    @strawberry.mutation
    def unlock_dm_conversation(
        self, info, conversation_id: strawberry.ID, lock_code: Optional[str] = None
    ) -> DmConversationType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        # If a code is supplied (view-time unlock gate), it must match.
        # No code = in-chat unlock by a participant who is already viewing.
        if lock_code is not None and conv.lock_code and conv.lock_code != lock_code:
            raise Exception("Incorrect lock code")
        conv.is_locked = False
        conv.lock_type = None
        conv.lock_code = None
        conv.save()
        return DmConversationType.from_model(conv, user)

    # ── Messages ──────────────────────────────────────────────────────────────

    @strawberry.mutation
    def send_dm_message(self, info, input: SendDmInput) -> DmMessageType:
        user = require_auth(info)
        conv = _get_conversation(user, input.conversationId)
        voice = None
        if input.voiceNote:
            voice = {
                "url": input.voiceNote.url,
                "duration": input.voiceNote.duration,
                "waveform": input.voiceNote.waveform or [],
            }
        msg = _create_message(
            conv, user,
            body=input.text or "",
            images=input.images or [],
            voice_note=voice,
            reply_to_id=input.replyToMessageId,
            disappear_after=input.disappearAfter,
        )
        return DmMessageType.from_model(msg)

    @strawberry.mutation
    def edit_dm_message(self, info, message_id: strawberry.ID, text: str) -> DmMessageType:
        user = require_auth(info)
        msg = Message.objects.filter(id=message_id, sender=user).first()
        if msg is None:
            raise Exception("Message not found")
        msg.body = text
        msg.is_edited = True
        msg.edited_at = timezone.now()
        msg.save(update_fields=["body", "is_edited", "edited_at", "updated_at"])
        return DmMessageType.from_model(msg)

    @strawberry.mutation
    def delete_dm_message(self, info, message_id: strawberry.ID) -> bool:
        user = require_auth(info)
        msg = Message.objects.filter(id=message_id).select_related("conversation").first()
        if msg is None:
            raise Exception("Message not found")
        msg.delete_for_user(user)
        return True

    @strawberry.mutation
    def add_dm_reaction(
        self, info, message_id: strawberry.ID, emoji: str
    ) -> DmMessageType:
        user = require_auth(info)
        msg = _get_reactable_message(user, message_id)
        MessageReaction.objects.get_or_create(
            message=msg, user=user, emoji=emoji,
            defaults={"tenant": getattr(user, "tenant", None)},
        )
        return DmMessageType.from_model(msg)

    @strawberry.mutation
    def remove_dm_reaction(
        self, info, message_id: strawberry.ID, emoji: str
    ) -> DmMessageType:
        user = require_auth(info)
        msg = _get_reactable_message(user, message_id)
        MessageReaction.objects.filter(message=msg, user=user, emoji=emoji).delete()
        return DmMessageType.from_model(msg)

    # ── Quick replies ─────────────────────────────────────────────────────────

    @strawberry.mutation
    def create_dm_quick_reply(
        self, info, text: str, title: Optional[str] = None
    ) -> DmQuickReplyType:
        user = require_auth(info)
        profile = creator_profile_of(user)
        if profile is None:
            raise Exception("Only creators can create quick replies")
        q = QuickReply.objects.create(
            creator=profile, tenant=getattr(user, "tenant", None),
            text=text, title=title,
        )
        return DmQuickReplyType.from_model(q)

    @strawberry.mutation
    def delete_dm_quick_reply(self, info, quick_reply_id: strawberry.ID) -> bool:
        user = require_auth(info)
        profile = creator_profile_of(user)
        if profile is not None:
            QuickReply.objects.filter(id=quick_reply_id, creator=profile).delete()
        return True

    @strawberry.mutation
    def use_dm_quick_reply(self, info, quick_reply_id: strawberry.ID) -> DmQuickReplyType:
        user = require_auth(info)
        profile = creator_profile_of(user)
        q = (
            QuickReply.objects.filter(id=quick_reply_id, creator=profile).first()
            if profile is not None
            else None
        )
        if q is None:
            raise Exception("Quick reply not found")
        q.usage_count += 1
        q.save(update_fields=["usage_count", "updated_at"])
        return DmQuickReplyType.from_model(q)

    # ── Scheduled messages ────────────────────────────────────────────────────

    @strawberry.mutation
    def schedule_dm_message(
        self, info, conversation_id: strawberry.ID, text: str, scheduled_for: datetime
    ) -> DmScheduledMessageType:
        user = require_auth(info)
        conv = _get_conversation(user, conversation_id)
        s = ScheduledMessage.objects.create(
            conversation=conv, sender=user,
            tenant=getattr(user, "tenant", None),
            text=text, scheduled_for=scheduled_for,
        )
        return DmScheduledMessageType.from_model(s)

    @strawberry.mutation
    def cancel_dm_scheduled_message(self, info, scheduled_message_id: strawberry.ID) -> bool:
        user = require_auth(info)
        ScheduledMessage.objects.filter(
            id=scheduled_message_id, sender=user, is_sent=False
        ).delete()
        return True


def _create_message(conv, sender, body="", images=None, voice_note=None,
                    reply_to_id=None, disappear_after=None):
    """Create a message, set type/expiry, and update conversation snapshot/unread."""
    if voice_note:
        mtype = MessageType.AUDIO
    elif images:
        mtype = MessageType.IMAGE
    else:
        mtype = MessageType.TEXT

    mode, expires_at = _compute_expiry(conv, disappear_after)
    msg = Message.objects.create(
        conversation=conv,
        tenant=conv.tenant,
        sender=sender,
        body=body or None,
        message_type=mtype,
        images=images or [],
        voice_note=voice_note,
        reply_to_message_id=reply_to_id,
        disappear_after=mode,
        expires_at=expires_at,
    )
    conv.update_last_message(msg)
    # increment unread for the recipient side
    recipient_side = 'creator' if conv.fan_id == sender.id else 'fan'
    conv.increment_unread_count(recipient_side)
    return msg


@strawberry.type
class MessagingMutations(DmMutations):
    pass
