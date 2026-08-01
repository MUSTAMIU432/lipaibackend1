import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import NotificationType, NotificationStatus, NotificationPriority, NotificationChannel


class Notification(TenantAwareModel):
    """
    Notifications - Module 17
    Core notification model matching the provided schema
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )

    # Content
    title = models.CharField(max_length=255)
    body = models.TextField()
    image_url = models.URLField(null=True, blank=True)
    action_url = models.URLField(null=True, blank=True)
    action_label = models.CharField(max_length=100, null=True, blank=True)

    # Source References (commented out until models exist)
    # triggered_by_user = models.ForeignKey(
    #     'lipaidox_auth.User',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='triggered_notifications'
    # )
    # content = models.ForeignKey(
    #     'lipaidox_content.Content',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )
    # live_stream = models.ForeignKey(
    #     'lipaidox_content.LiveStream',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )
    # announcement = models.ForeignKey(
    #     'lipaidox_content.Announcement',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )
    # tip = models.ForeignKey(
    #     'lipaidox_monetization.Tip',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )
    # subscription = models.ForeignKey(
    #     'lipaidox_monetization.Subscription',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )
    # payout = models.ForeignKey(
    #     'lipaidox_monetization.PayoutTransaction',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notifications'
    # )

    # Status
    status = models.CharField(
        max_length=15,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    # Grouping
    group_key = models.CharField(max_length=100, null=True, blank=True)
    group_count = models.IntegerField(default=1)

    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['user'], name='idx_notifications_user_id'),
            models.Index(fields=['notification_type'], name='idx_notifications_type'),
            models.Index(fields=['status'], name='idx_notifications_status'),
            models.Index(fields=['is_read'], name='idx_notifications_is_read'),
            models.Index(fields=['priority'], name='idx_notifications_priority'),
            models.Index(fields=['created_at'], name='idx_notifications_created_at'),
            models.Index(fields=['user', 'group_key'], name='idx_notifications_group_key'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(group_count__gte=1),
                name='group_count_check'
            ),
        ]

    def __str__(self):
        return f"Notification: {self.user.username} - {self.title}"

    def mark_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        
        self.is_read = True
        self.read_at = timezone.now()
        self.status = NotificationStatus.READ
        self.save()

    def dismiss(self):
        """Dismiss notification"""
        from django.utils import timezone
        
        self.is_read = True
        self.dismissed_at = timezone.now()
        self.status = NotificationStatus.DISMISSED
        self.save()

    def mark_sent(self):
        """Mark notification as sent"""
        from django.utils import timezone
        
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        self.save()

    def is_expired(self):
        """Check if notification is expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @classmethod
    def create_notification(cls, user, title, body, notification_type, **kwargs):
        """Create a new notification"""
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            title=title,
            body=body,
            notification_type=notification_type,
            **kwargs
        )

    @classmethod
    def get_user_notifications(cls, user, unread_only=False, limit=50):
        """Get user's notifications"""
        queryset = cls.objects.filter(user=user)
        
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        # Filter out expired notifications
        from django.utils import timezone
        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )
        
        return queryset.order_by('-priority', '-created_at')[:limit]

    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count for user"""
        from django.utils import timezone
        
        return cls.objects.filter(
            user=user,
            is_read=False
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        ).count()

    @classmethod
    def mark_all_read(cls, user):
        """Mark all notifications as read for user"""
        from django.utils import timezone
        
        notifications = cls.objects.filter(
            user=user,
            is_read=False
        )
        
        count = notifications.count()
        notifications.update(is_read=True, read_at=timezone.now(), status=NotificationStatus.READ)
        
        return count

    @classmethod
    def cleanup_expired_notifications(cls):
        """Delete expired notifications"""
        from django.utils import timezone
        
        return cls.objects.filter(
            expires_at__lte=timezone.now()
        ).delete()[0]

    @classmethod
    def bulk_create_notifications(cls, users, title, body, notification_type, **kwargs):
        """Create notifications for multiple users"""
        notifications = []
        for user in users:
            notifications.append(cls(
                user=user,
                tenant=user.tenant,
                title=title,
                body=body,
                notification_type=notification_type,
                **kwargs
            ))
        
        return cls.objects.bulk_create(notifications)

    @classmethod
    def create_grouped_notification(cls, users, title, body, notification_type, group_key, **kwargs):
        """Create grouped notifications"""
        notifications = []
        for user in users:
            notifications.append(cls(
                user=user,
                tenant=user.tenant,
                title=title,
                body=body,
                notification_type=notification_type,
                group_key=group_key,
                **kwargs
            ))
        
        created = cls.objects.bulk_create(notifications)
        
        # Update group counts
        cls.objects.filter(group_key=group_key).update(group_count=len(created))
        
        return created
