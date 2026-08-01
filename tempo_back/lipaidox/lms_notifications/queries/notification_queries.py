import strawberry
from typing import List, Optional
from ..schema.notification_types import LmsNotificationNode
from ..models.notification import LmsNotification

@strawberry.type
class NotificationQueries:
    @strawberry.field
    def my_notifications(
        self,
        info,
        unread_only: bool = False,
        limit: int = 20
    ) -> List[LmsNotificationNode]:
        """Get notifications for the current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        notifications = LmsNotification.get_user_notifications(
            user=user,
            unread_only=unread_only,
            limit=limit
        )
        return [LmsNotificationNode.from_model(notif) for notif in notifications]
    
    @strawberry.field
    def unread_notifications_count(self, info) -> int:
        """Get unread notification count for the current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return 0
        
        return LmsNotification.get_unread_count(user)
    
    @strawberry.field
    def notification_detail(
        self,
        info,
        notification_id: strawberry.ID
    ) -> Optional[LmsNotificationNode]:
        """Get notification details"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            notification = LmsNotification.objects.get(id=notification_id, user=user)
            return LmsNotificationNode.from_model(notification)
        except LmsNotification.DoesNotExist:
            return None
    
    @strawberry.field
    def notification_types(self, info) -> List[str]:
        """Get available notification types"""
        if not info.context.request.user.is_authenticated:
            return []
        
        return [choice.value for choice in NotificationType.choices]
