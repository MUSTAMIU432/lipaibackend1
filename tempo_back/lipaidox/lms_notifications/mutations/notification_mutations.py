import strawberry
from typing import Optional
from ..schema.notification_types import LmsNotificationNode
from ..models.notification import LmsNotification, NotificationType

@strawberry.type
class NotificationMutations:
    @strawberry.mutation
    def mark_notification_read(
        self,
        info,
        notification_id: strawberry.ID
    ) -> LmsNotificationNode:
        """Mark a specific notification as read"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            notification = LmsNotification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return LmsNotificationNode.from_model(notification)
        except LmsNotification.DoesNotExist:
            raise Exception("Notification not found")
    
    @strawberry.mutation
    def mark_all_notifications_read(self, info) -> int:
        """Mark all notifications as read for the user"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        count = LmsNotification.mark_all_read(user)
        return count
    
    @strawberry.mutation
    def create_notification(
        self,
        info,
        user_id: strawberry.ID,
        type: str,
        title: str,
        body: str,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        metadata_json: Optional[str] = None  # Accept JSON string instead of dict
    ) -> LmsNotificationNode:
        """Create a new notification (admin/instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user has permission to create notifications
        # This is a simplified check - in production you'd check roles
        if not (user.is_staff or hasattr(user, 'instructor_profile')):
            raise Exception("Permission denied")
        
        try:
            from lipaidox_auth.models import User
            import json
            target_user = User.objects.get(id=user_id)
            
            # Validate notification type
            try:
                notification_type = NotificationType(type)
            except ValueError:
                raise Exception("Invalid notification type")
            
            # Parse metadata JSON if provided
            metadata_dict = {}
            if metadata_json:
                try:
                    metadata_dict = json.loads(metadata_json)
                except json.JSONDecodeError:
                    raise Exception("Invalid metadata JSON")
            
            notification = LmsNotification.create_notification(
                user=target_user,
                notification_type=notification_type,
                title=title,
                body=body,
                action_url=action_url,
                action_text=action_text,
                metadata=metadata_dict
            )
            
            return LmsNotificationNode.from_model(notification)
        except User.DoesNotExist:
            raise Exception("User not found")
    
    @strawberry.mutation
    def delete_notification(
        self,
        info,
        notification_id: strawberry.ID
    ) -> bool:
        """Delete a notification"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            notification = LmsNotification.objects.get(id=notification_id, user=user)
            notification.delete()
            return True
        except LmsNotification.DoesNotExist:
            raise Exception("Notification not found")
