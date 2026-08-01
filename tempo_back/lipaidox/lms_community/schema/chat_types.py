import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.chat import StudyRoomChannel, StudyRoomMessage, MessageReaction

@strawberry.type
class MessageReactionNode:
    id: strawberry.ID
    emoji: str
    username: str
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: MessageReaction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            emoji=instance.emoji,
            username=instance.user.username,
            createdAt=instance.created_at,
        )

@strawberry.type
class StudyRoomMessageNode:
    id: strawberry.ID
    content: str
    messageType: str
    username: str
    replyTo: Optional["StudyRoomMessageNode"]
    isPinned: bool
    createdAt: datetime
    reactions: List[MessageReactionNode]

    @classmethod
    def from_model(cls, instance: StudyRoomMessage):
        return cls(
            id=strawberry.ID(str(instance.id)),
            content=instance.content,
            messageType=instance.message_type,
            username=instance.user.username,
            replyTo=cls.from_model(instance.reply_to) if instance.reply_to else None,
            isPinned=instance.is_pinned,
            createdAt=instance.created_at,
            reactions=[MessageReactionNode.from_model(r) for r in instance.reactions.all()],
        )

@strawberry.type
class StudyRoomChannelNode:
    id: strawberry.ID
    name: str
    channelType: str
    description: Optional[str]
    isPrivate: bool
    createdAt: datetime
    messages: List[StudyRoomMessageNode]

    @classmethod
    def from_model(cls, instance: StudyRoomChannel):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            channelType=instance.channel_type,
            description=instance.description,
            isPrivate=instance.is_private,
            createdAt=instance.created_at,
            messages=[StudyRoomMessageNode.from_model(m) for m in instance.messages.all()],
        )
