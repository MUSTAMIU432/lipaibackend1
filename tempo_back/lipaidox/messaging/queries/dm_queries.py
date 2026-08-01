import strawberry
from typing import List, Optional
from django.db.models import Q

from ..models import Conversation, Message, QuickReply, ScheduledMessage
from ..schema.types import (
    DmConversationType,
    DmMessageType,
    DmQuickReplyType,
    DmScheduledMessageType,
    DmMediaItemType,
)
from ..schema.helpers import require_auth, get_user, side_of, creator_profile_of


@strawberry.type
class DmQueries:

    @strawberry.field
    def dm_conversations(
        self, info, search: Optional[str] = None
    ) -> List[DmConversationType]:
        user = get_user(info)
        if user is None:
            return []
        qs = Conversation.objects.filter(
            Q(fan=user) | Q(creator=user)
        ).exclude(status="deleted")
        # hide locked + per-side hidden, unless searched
        if search:
            term = search.strip()
            qs = qs.filter(
                Q(fan__username__icontains=term)
                | Q(creator__username__icontains=term)
                | Q(fan__first_name__icontains=term)
                | Q(creator__first_name__icontains=term)
                | Q(secret_name__iexact=term)
            )
        else:
            # hide per-side hidden chats; locked chats stay (rendered blurred client-side)
            qs = qs.filter(
                ~(Q(fan=user) & Q(hidden_by_fan=True)),
                ~(Q(creator=user) & Q(hidden_by_creator=True)),
            )
        qs = qs.select_related("fan", "creator").order_by("-last_message_at")
        convos = list(qs)
        # pinned first (per-side)
        def is_pinned(c):
            return c.pinned_by_fan if c.fan_id == user.id else c.pinned_by_creator
        convos.sort(key=lambda c: (not is_pinned(c)))
        return [DmConversationType.from_model(c, user) for c in convos]

    @strawberry.field
    def dm_conversation(
        self, info, conversation_id: strawberry.ID
    ) -> Optional[DmConversationType]:
        user = get_user(info)
        if user is None:
            return None
        c = Conversation.objects.filter(
            Q(id=conversation_id) & (Q(fan=user) | Q(creator=user))
        ).select_related("fan", "creator").first()
        return DmConversationType.from_model(c, user) if c else None

    @strawberry.field
    def dm_conversation_by_secret_name(
        self, info, secret_name: str
    ) -> Optional[DmConversationType]:
        user = get_user(info)
        if user is None:
            return None
        c = Conversation.objects.filter(
            (Q(fan=user) | Q(creator=user)),
            secret_name__iexact=secret_name.strip(),
        ).select_related("fan", "creator").first()
        return DmConversationType.from_model(c, user) if c else None

    @strawberry.field
    def dm_messages(
        self,
        info,
        conversation_id: strawberry.ID,
        limit: int = 50,
        before: Optional[str] = None,
        after: Optional[str] = None,   # ISO timestamp — return only messages newer than this
    ) -> List[DmMessageType]:
        user = get_user(info)
        if user is None:
            return []
        conv = Conversation.objects.filter(
            Q(id=conversation_id) & (Q(fan=user) | Q(creator=user))
        ).first()
        if conv is None:
            return []
        side = side_of(conv, user)
        cleared_at = conv.cleared_at_fan if side == 'fan' else conv.cleared_at_creator

        qs = Message.objects.filter(conversation=conv).exclude(status="deleted")
        qs = qs.exclude(Q(sender=user) & Q(is_deleted_by_sender=True))
        qs = qs.exclude(~Q(sender=user) & Q(is_deleted_by_receiver=True))
        if cleared_at:
            qs = qs.filter(sent_at__gt=cleared_at)
        if before:
            qs = qs.filter(sent_at__lt=before)
        if after:
            qs = qs.filter(sent_at__gt=after)
        qs = qs.select_related("reply_to_message", "sender").prefetch_related("reactions").order_by("-sent_at")[:limit]
        return [DmMessageType.from_model(m) for m in reversed(list(qs))]

    @strawberry.field
    def dm_quick_replies(self, info) -> List[DmQuickReplyType]:
        user = get_user(info)
        if user is None:
            return []
        profile = creator_profile_of(user)
        if profile is None:
            return []
        qs = QuickReply.objects.filter(creator=profile).order_by("-usage_count", "-created_at")
        return [DmQuickReplyType.from_model(q) for q in qs]

    @strawberry.field
    def dm_scheduled_messages(
        self, info, conversation_id: Optional[strawberry.ID] = None
    ) -> List[DmScheduledMessageType]:
        user = get_user(info)
        if user is None:
            return []
        qs = ScheduledMessage.objects.filter(sender=user, is_sent=False)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        qs = qs.order_by("scheduled_for")
        return [DmScheduledMessageType.from_model(s) for s in qs]

    @strawberry.field
    def dm_conversation_media(
        self, info, conversation_id: strawberry.ID
    ) -> List[DmMediaItemType]:
        user = get_user(info)
        if user is None:
            return []
        conv = Conversation.objects.filter(
            Q(id=conversation_id) & (Q(fan=user) | Q(creator=user))
        ).first()
        if conv is None:
            return []
        items: List[DmMediaItemType] = []
        msgs = Message.objects.filter(conversation=conv).exclude(status="deleted").order_by("-sent_at")
        for m in msgs:
            for url in (m.images or []):
                items.append(DmMediaItemType(type="image", url=url, timestamp=m.sent_at, messageId=strawberry.ID(str(m.id))))
            if m.voice_note and m.voice_note.get("url"):
                items.append(DmMediaItemType(type="voice", url=m.voice_note["url"], timestamp=m.sent_at, messageId=strawberry.ID(str(m.id))))
            if m.video_note and m.video_note.get("url"):
                items.append(DmMediaItemType(type="video", url=m.video_note["url"], timestamp=m.sent_at, messageId=strawberry.ID(str(m.id))))
        return items


@strawberry.type
class MessagingQueries(DmQueries):
    pass
