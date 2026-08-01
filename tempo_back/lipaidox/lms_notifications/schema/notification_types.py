import strawberry
from datetime import datetime
from typing import Optional, List
from ..models.notification import LmsNotification

@strawberry.type
class NotificationMetadata:
    courseId: Optional[str]
    courseTitle: Optional[str]
    assignmentId: Optional[str]
    assignmentTitle: Optional[str]
    # Add other metadata fields as needed

@strawberry.type
class LmsNotificationNode:
    id: strawberry.ID
    userId: strawberry.ID
    type: str
    title: str
    body: str
    actionUrl: Optional[str]
    actionText: Optional[str]
    isRead: bool
    readAt: Optional[datetime]
    metadata: Optional[NotificationMetadata]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: LmsNotification):
        # Convert metadata dict to NotificationMetadata object
        metadata_obj = None
        if instance.metadata:
            metadata_obj = NotificationMetadata(
                courseId=instance.metadata.get('course_id'),
                courseTitle=instance.metadata.get('course_title'),
                assignmentId=instance.metadata.get('assignment_id'),
                assignmentTitle=instance.metadata.get('assignment_title')
            )
        
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user.id)),
            type=instance.notification_type,
            title=instance.title,
            body=instance.body,
            actionUrl=instance.action_url,
            actionText=instance.action_text,
            isRead=instance.is_read,
            readAt=instance.read_at,
            metadata=metadata_obj,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )
