import strawberry
from typing import Optional
from ..schema.chat_types import StudyRoomChannelNode, StudyRoomMessageNode, MessageReactionNode
from ..models.chat import StudyRoomChannel, StudyRoomMessage, MessageReaction, ChannelType, MessageType
from ..models.study_room import StudyRoomMember

@strawberry.type
class ChatMutations:
    @strawberry.mutation
    def create_channel(
        self,
        info,
        room_id: strawberry.ID,
        name: str,
        channel_type: str = "text",
        description: Optional[str] = None,
        is_private: bool = False
    ) -> StudyRoomChannelNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is room member
        room_member = StudyRoomMember.objects.filter(
            room_id=room_id, 
            student__user=user
        ).first()
        if not room_member:
            raise Exception("Not a member of this room")
        
        channel = StudyRoomChannel.objects.create(
            room_id=room_id,
            name=name,
            channel_type=channel_type,
            description=description,
            is_private=is_private,
            tenant=user.tenant
        )
        return StudyRoomChannelNode.from_model(channel)

    @strawberry.mutation
    def send_message(
        self,
        info,
        channel_id: strawberry.ID,
        content: str,
        message_type: str = "text",
        reply_to_id: Optional[strawberry.ID] = None
    ) -> StudyRoomMessageNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        channel = StudyRoomChannel.objects.get(id=channel_id)
        
        # Check if user is room member
        room_member = StudyRoomMember.objects.filter(
            room=channel.room, 
            student__user=user
        ).first()
        if not room_member:
            raise Exception("Not a member of this room")
        
        reply_to = None
        if reply_to_id:
            reply_to = StudyRoomMessage.objects.get(id=reply_to_id)
        
        message = StudyRoomMessage.objects.create(
            channel=channel,
            user=user,
            content=content,
            message_type=message_type,
            reply_to=reply_to
        )
        return StudyRoomMessageNode.from_model(message)

    @strawberry.mutation
    def add_reaction(
        self,
        info,
        message_id: strawberry.ID,
        emoji: str
    ) -> MessageReactionNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        message = StudyRoomMessage.objects.get(id=message_id)
        
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=user,
            emoji=emoji
        )
        return MessageReactionNode.from_model(reaction)

    @strawberry.mutation
    def toggle_pin_message(self, info, message_id: strawberry.ID) -> StudyRoomMessageNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        message = StudyRoomMessage.objects.get(id=message_id)
        channel = message.channel
        
        # Check if user is moderator or owner
        room_member = StudyRoomMember.objects.filter(
            room=channel.room, 
            student__user=user,
            role__in=['owner', 'moderator']
        ).first()
        if not room_member:
            raise Exception("Insufficient permissions")
        
        message.is_pinned = not message.is_pinned
        message.save()
        return StudyRoomMessageNode.from_model(message)
