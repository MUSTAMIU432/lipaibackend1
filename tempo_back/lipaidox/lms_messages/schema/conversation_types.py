import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.conversation import Conversation

@strawberry.type
class ConversationNode:
    id: strawberry.ID
    courseId: strawberry.ID
    courseTitle: str
    studentId: strawberry.ID
    studentName: str
    instructorId: strawberry.ID
    instructorName: str
    isActive: bool
    endedAt: Optional[datetime]
    endedBy: Optional[str]
    createdAt: datetime
    lastMessageAt: Optional[datetime]
    unreadCount: int

    @classmethod
    def from_model(cls, instance: Conversation, user=None):
        # Calculate unread count for user
        unread_count = 0
        if user:
            from ..models.message import Message
            unread_count = Message.get_unread_count(instance, user)
        
        return cls(
            id=strawberry.ID(str(instance.id)),
            courseId=strawberry.ID(str(instance.course.id)),
            courseTitle=instance.course.title,
            studentId=strawberry.ID(str(instance.student.id)),
            studentName=instance.student.user.username,
            instructorId=strawberry.ID(str(instance.instructor.id)),
            instructorName=instance.instructor.username,
            isActive=instance.is_active,
            endedAt=instance.ended_at,
            endedBy=instance.ended_by.username if instance.ended_by else None,
            createdAt=instance.created_at,
            lastMessageAt=instance.last_message_at,
            unreadCount=unread_count,
        )
