import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.message import Message

@strawberry.type
class MessageAttachmentNode:
    id: strawberry.ID
    fileUrl: str
    fileName: str
    fileType: str
    fileSize: int
    uploadedAt: datetime

    @classmethod
    def from_model(cls, instance):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fileUrl=instance.file_url,
            fileName=instance.file_name,
            fileType=instance.file_type,
            fileSize=instance.file_size,
            uploadedAt=instance.uploaded_at,
        )

@strawberry.type
class MessageNode:
    id: strawberry.ID
    conversationId: strawberry.ID
    senderId: strawberry.ID
    senderName: str
    content: str
    messageType: str
    readAt: Optional[datetime]
    sentAt: datetime
    attachments: List[MessageAttachmentNode]

    @classmethod
    def from_model(cls, instance: Message):
        return cls(
            id=strawberry.ID(str(instance.id)),
            conversationId=strawberry.ID(str(instance.conversation.id)),
            senderId=strawberry.ID(str(instance.sender.id)),
            senderName=instance.sender.username,
            content=instance.content,
            messageType=instance.message_type,
            readAt=instance.read_at,
            sentAt=instance.sent_at,
            attachments=[MessageAttachmentNode.from_model(att) for att in instance.attachments.all()],
        )
