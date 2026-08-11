import strawberry
from strawberry.scalars import JSON
from typing import Optional, List
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from datetime import timedelta, date

from ..models import (
    Notification, NotificationType, NotificationPriority,
    NotificationQueue, DeliveryChannel, NotificationStatus,
    NotificationPreference,
    NotificationTemplate, NotificationDeliveryLog
)

from ..schema.notification_schema import (
    # Types
    NotificationType as NotificationGraphQLType, NotificationQueueType,
    NotificationPreferenceType, NotificationTemplateType,
    NotificationDeliveryLogType, NotificationStats,
    
    # Input Types
    NotificationCreateInput, BulkNotificationInput,
    NotificationPreferencesUpdateInput, NotificationFilterInput
)

from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_admin(user):
    """Check if user is admin"""
    if user.role not in [UserRoles.ADMIN, 'superadmin']:
        raise Exception("Admin access required")
    return True


@strawberry.type
class NotificationQuery:
    # Notification Queries
    @strawberry.field
    def my_notifications(
        self,
        info: strawberry.types.Info,
        filter: Optional[NotificationFilterInput] = None
    ) -> List[NotificationGraphQLType]:
        """Get current user's notifications"""
        user = require_auth(info)
        
        unread_only = filter.unreadOnly if filter else False
        limit = filter.limit if filter else 50
        
        notifications = Notification.get_user_notifications(
            user=user,
            unread_only=unread_only,
            limit=limit
        )
        
        # Apply additional filters
        if filter:
            if filter.notificationType:
                notifications = notifications.filter(notification_type=filter.notificationType)
            if filter.priority:
                notifications = notifications.filter(priority=filter.priority)
        
        return [NotificationGraphQLType.from_model(notification) for notification in notifications]

    @strawberry.field
    def unread_notification_count(self, info: strawberry.types.Info) -> int:
        """Get unread notification count for current user"""
        user = require_auth(info)
        
        return Notification.get_unread_count(user)

    @strawberry.field
    def notification_stats(self, info: strawberry.types.Info) -> NotificationStats:
        """Get notification statistics for current user"""
        user = require_auth(info)
        
        # Get user's notifications
        notifications = Notification.objects.filter(recipient=user)
        
        # Filter out expired notifications
        from django.utils import timezone
        notifications = notifications.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        
        total_notifications = notifications.count()
        unread_count = notifications.filter(is_read=False).count()
        
        # Stats by type
        by_type = notifications.values('notification_type').annotate(count=Count('id'))
        by_type_dict = {item['notification_type']: item['count'] for item in by_type}
        
        # Stats by priority
        by_priority = notifications.values('priority').annotate(count=Count('id'))
        by_priority_dict = {item['priority']: item['count'] for item in by_priority}
        
        # Delivery stats
        delivery_stats = NotificationDeliveryLog.get_delivery_stats(days=30)
        
        return NotificationStats(
            totalNotifications=total_notifications,
            unreadCount=unread_count,
            byType=by_type_dict,
            byPriority=by_priority_dict,
            deliveryStats=delivery_stats
        )

    # Notification Preferences Queries
    @strawberry.field
    def my_notification_preferences(self, info: strawberry.types.Info) -> NotificationPreferenceType:
        """Get current user's notification preferences"""
        user = require_auth(info)
        
        preferences = NotificationPreference.get_or_create_for_user(user)
        
        return NotificationPreferenceType.from_model(preferences)

    # Template Queries
    @strawberry.field
    def notification_templates(
        self,
        info: strawberry.types.Info,
        notificationType: Optional[str] = None,
        channel: Optional[str] = None
    ) -> List[NotificationTemplateType]:
        """Get notification templates (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = NotificationTemplate.objects.filter(
            tenant=user.tenant,
            is_active=True
        )
        
        if notificationType:
            queryset = queryset.filter(notification_type=notificationType)
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        return [NotificationTemplateType.from_model(template) for template in queryset]

    # Queue and Delivery Queries
    @strawberry.field
    def notification_queue(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 100
    ) -> List[NotificationQueueType]:
        """Get notification queue (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = NotificationQueue.objects.filter(tenant=user.tenant)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        queue_items = queryset.order_by('-priority', 'created_at')[:limit]
        
        return [NotificationQueueType.from_model(item) for item in queue_items]

    @strawberry.field
    def delivery_logs(
        self,
        info: strawberry.types.Info,
        notificationId: Optional[strawberry.ID] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        days: int = 7,
        limit: int = 100
    ) -> List[NotificationDeliveryLogType]:
        """Get notification delivery logs (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = NotificationDeliveryLog.objects.filter(tenant=user.tenant)
        
        if notificationId:
            queryset = queryset.filter(notification_id=notificationId)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        if days:
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        logs = queryset.order_by('-created_at')[:limit]
        
        return [NotificationDeliveryLogType.from_model(log) for log in logs]

    # Platform Statistics
    @strawberry.field
    def platform_notification_stats(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> JSON:
        """Get platform notification statistics (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Overall stats
        total_notifications = Notification.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        ).count()
        
        total_delivered = NotificationDeliveryLog.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date,
            status=NotificationStatus.DELIVERED
        ).count()
        
        # By type
        by_type = Notification.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        ).values('notification_type').annotate(count=Count('id'))
        
        # By channel
        by_channel = NotificationDeliveryLog.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        ).values('channel').annotate(count=Count('id'))
        
        # Queue stats
        queue_stats = NotificationQueue.objects.filter(
            tenant=user.tenant
        ).values('status').annotate(count=Count('id'))
        
        return {
            'period_days': days,
            'total_notifications': total_notifications,
            'total_delivered': total_delivered,
            'delivery_rate': (total_delivered / total_notifications * 100) if total_notifications > 0 else 0,
            'by_type': {item['notification_type']: item['count'] for item in by_type},
            'by_channel': {item['channel']: item['count'] for item in by_channel},
            'queue_stats': {item['status']: item['count'] for item in queue_stats}
        }

    @strawberry.field
    def notification_engagement_stats(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> JSON:
        """Get notification engagement statistics (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Read rates by type
        notifications = Notification.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        )
        
        total_by_type = notifications.values('notification_type').annotate(total=Count('id'))
        read_by_type = notifications.filter(is_read=True).values('notification_type').annotate(read=Count('id'))
        
        # Calculate read rates
        engagement_stats = {}
        for type_stat in total_by_type:
            notification_type = type_stat['notification_type']
            total = type_stat['total']
            
            read_count = 0
            for read_stat in read_by_type:
                if read_stat['notification_type'] == notification_type:
                    read_count = read_stat['read']
                    break
            
            engagement_stats[notification_type] = {
                'total': total,
                'read': read_count,
                'read_rate': (read_count / total * 100) if total > 0 else 0
            }
        
        # Average read time
        read_notifications = notifications.filter(
            is_read=True,
            read_at__isnull=False
        )
        
        if read_notifications.exists():
            avg_read_time = read_notifications.aggregate(
                avg_time=Avg(F('read_at') - F('created_at'))
            )['avg_time']
        else:
            avg_read_time = None
        
        return {
            'period_days': days,
            'engagement_by_type': engagement_stats,
            'average_read_time': avg_read_time.total_seconds() / 3600 if avg_read_time else None  # in hours
        }
