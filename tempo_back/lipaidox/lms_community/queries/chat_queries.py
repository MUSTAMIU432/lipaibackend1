import strawberry
from typing import List, Optional
from ..schema.chat_types import StudyRoomChannelNode, StudyRoomMessageNode
from ..models.chat import StudyRoomChannel, StudyRoomMessage

@strawberry.type
class ChatQueries:
    @strawberry.field
    def room_channels(self, room_id: strawberry.ID) -> List[StudyRoomChannelNode]:
        return [StudyRoomChannelNode.from_model(c) for c in StudyRoomChannel.objects.filter(room_id=room_id)]

    @strawberry.field
    def channel_messages(self, channel_id: strawberry.ID, limit: int = 50) -> List[StudyRoomMessageNode]:
        messages = StudyRoomMessage.objects.filter(channel_id=channel_id).order_by('-created_at')[:limit]
        return [StudyRoomMessageNode.from_model(m) for m in reversed(list(messages))]

    @strawberry.field
    def pinned_messages(self, channel_id: strawberry.ID) -> List[StudyRoomMessageNode]:
        return [StudyRoomMessageNode.from_model(m) for m in StudyRoomMessage.objects.filter(channel_id=channel_id, is_pinned=True).order_by('-created_at')]

    @strawberry.field
    def message_replies(self, message_id: strawberry.ID) -> List[StudyRoomMessageNode]:
        return [StudyRoomMessageNode.from_model(m) for m in StudyRoomMessage.objects.filter(reply_to_id=message_id).order_by('created_at')]
