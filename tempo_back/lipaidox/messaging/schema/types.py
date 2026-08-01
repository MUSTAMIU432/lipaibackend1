import strawberry
from datetime import datetime
from typing import List, Optional

from ..models import Conversation, Message, QuickReply, ScheduledMessage
from .helpers import side_of, other_party, display_name, avatar_url


# ─── Leaf types ───────────────────────────────────────────────────────────────

@strawberry.type
class DmUserType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isOnline: bool
    lastSeen: Optional[str]

    @classmethod
    def from_model(cls, user):
        from django.utils import timezone
        from datetime import timedelta
        last = getattr(user, 'last_login', None)
        online = (last is not None and (timezone.now() - last) < timedelta(minutes=5))
        last_seen_str = last.isoformat() if last else None
        return cls(
            id=strawberry.ID(str(user.id)),
            username=user.username,
            displayName=display_name(user),
            avatar=avatar_url(user),
            isOnline=online,
            lastSeen=last_seen_str,
        )


@strawberry.type
class DmReactionType:
    emoji: str
    count: int
    userIds: List[str]


@strawberry.type
class DmReplyType:
    messageId: strawberry.ID
    senderName: str
    content: str


@strawberry.type
class DmLinkType:
    url: str
    title: str
    description: str
    image: Optional[str]
    domain: str


@strawberry.type
class DmVoiceNoteType:
    url: str
    duration: int
    waveform: Optional[List[float]]


@strawberry.type
class DmVideoNoteType:
    url: str
    duration: int
    thumbnail: Optional[str]


@strawberry.type
class DmMediaItemType:
    type: str
    url: str
    timestamp: datetime
    messageId: strawberry.ID


# ─── Message ──────────────────────────────────────────────────────────────────

@strawberry.type
class DmMessageType:
    id: strawberry.ID
    conversationId: strawberry.ID
    senderId: strawberry.ID
    text: str
    timestamp: datetime
    images: List[str]
    reactions: List[DmReactionType]
    replyTo: Optional[DmReplyType]
    isEdited: bool
    editedAt: Optional[datetime]
    isDeleted: bool
    links: List[DmLinkType]
    disappearAfter: str
    expiresAt: Optional[datetime]
    voiceNote: Optional[DmVoiceNoteType]
    videoNote: Optional[DmVideoNoteType]
    status: str

    @classmethod
    def from_model(cls, m: Message) -> "DmMessageType":
        # aggregate reactions by emoji
        agg: dict = {}
        for r in m.reactions.all():
            entry = agg.setdefault(r.emoji, [])
            entry.append(str(r.user_id))
        reactions = [
            DmReactionType(emoji=e, count=len(ids), userIds=ids)
            for e, ids in agg.items()
        ]

        reply = None
        if m.reply_to_message_id and m.reply_to_message:
            rm = m.reply_to_message
            reply = DmReplyType(
                messageId=strawberry.ID(str(rm.id)),
                senderName=display_name(rm.sender),
                content=(rm.body or "")[:120],
            )

        links = [
            DmLinkType(
                url=l.get("url", ""),
                title=l.get("title", ""),
                description=l.get("description", ""),
                image=l.get("image"),
                domain=l.get("domain", ""),
            )
            for l in (m.links or [])
        ]

        voice = None
        if m.voice_note:
            voice = DmVoiceNoteType(
                url=m.voice_note.get("url", ""),
                duration=int(m.voice_note.get("duration", 0)),
                waveform=m.voice_note.get("waveform"),
            )

        video = None
        if m.video_note:
            video = DmVideoNoteType(
                url=m.video_note.get("url", ""),
                duration=int(m.video_note.get("duration", 0)),
                thumbnail=m.video_note.get("thumbnail"),
            )

        return cls(
            id=strawberry.ID(str(m.id)),
            conversationId=strawberry.ID(str(m.conversation_id)),
            senderId=strawberry.ID(str(m.sender_id)),
            text=m.body or "",
            timestamp=m.sent_at,
            images=m.images or [],
            reactions=reactions,
            replyTo=reply,
            isEdited=m.is_edited,
            editedAt=m.edited_at,
            isDeleted=(m.status == "deleted"),
            links=links,
            disappearAfter=m.disappear_after or "off",
            expiresAt=m.expires_at,
            voiceNote=voice,
            videoNote=video,
            status=m.status,
        )


# ─── Conversation ─────────────────────────────────────────────────────────────

@strawberry.type
class DmConversationType:
    id: strawberry.ID
    otherUser: DmUserType
    lastMessage: Optional[DmMessageType]
    lastMessageTime: Optional[datetime]
    unreadCount: int
    isPinned: bool
    isMuted: bool
    isHidden: bool
    isLocked: bool
    lockType: Optional[str]
    secretName: Optional[str]
    disappearingEnabled: str
    disappearingDurationMs: Optional[int]
    status: str

    @classmethod
    def from_model(cls, c: Conversation, user) -> "DmConversationType":
        side = side_of(c, user)
        last = (
            c.messages.exclude(status="deleted")
            .order_by("-sent_at")
            .first()
        )
        return cls(
            id=strawberry.ID(str(c.id)),
            otherUser=DmUserType.from_model(other_party(c, user)),
            lastMessage=DmMessageType.from_model(last) if last else None,
            lastMessageTime=c.last_message_at,
            unreadCount=(c.fan_unread_count if side == 'fan' else c.creator_unread_count),
            isPinned=(c.pinned_by_fan if side == 'fan' else c.pinned_by_creator),
            isMuted=(c.muted_by_fan if side == 'fan' else c.muted_by_creator),
            isHidden=(c.hidden_by_fan if side == 'fan' else c.hidden_by_creator),
            isLocked=c.is_locked,
            lockType=c.lock_type,
            secretName=c.secret_name,
            disappearingEnabled=c.disappearing_enabled or "off",
            disappearingDurationMs=c.disappearing_duration_ms,
            status=c.status,
        )


# ─── Quick replies & scheduled ────────────────────────────────────────────────

@strawberry.type
class DmQuickReplyType:
    id: strawberry.ID
    title: Optional[str]
    text: str
    usageCount: int
    createdAt: datetime

    @classmethod
    def from_model(cls, q: QuickReply) -> "DmQuickReplyType":
        return cls(
            id=strawberry.ID(str(q.id)),
            title=q.title,
            text=q.text,
            usageCount=q.usage_count,
            createdAt=q.created_at,
        )


@strawberry.type
class DmScheduledMessageType:
    id: strawberry.ID
    conversationId: strawberry.ID
    senderId: strawberry.ID
    text: str
    scheduledFor: datetime
    createdAt: datetime
    isSent: bool
    sentAt: Optional[datetime]

    @classmethod
    def from_model(cls, s: ScheduledMessage) -> "DmScheduledMessageType":
        return cls(
            id=strawberry.ID(str(s.id)),
            conversationId=strawberry.ID(str(s.conversation_id)),
            senderId=strawberry.ID(str(s.sender_id)),
            text=s.text,
            scheduledFor=s.scheduled_for,
            createdAt=s.created_at,
            isSent=s.is_sent,
            sentAt=s.sent_at,
        )


# ─── Inputs ───────────────────────────────────────────────────────────────────

@strawberry.input
class VoiceNoteInput:
    url: str
    duration: int
    waveform: Optional[List[float]] = None


@strawberry.input
class SendDmInput:
    conversationId: strawberry.ID
    text: Optional[str] = None
    images: Optional[List[str]] = None
    replyToMessageId: Optional[strawberry.ID] = None
    voiceNote: Optional[VoiceNoteInput] = None
    disappearAfter: Optional[str] = None
