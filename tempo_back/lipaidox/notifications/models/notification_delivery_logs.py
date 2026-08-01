import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import NotificationChannel, NotificationStatus


class NotificationDeliveryLog(TenantAwareModel):
    """
    Notification Delivery Logs - Module 17
    Tracks delivery attempts per channel for every notification
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        'Notification',
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='notification_delivery_logs'
    )
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices
    )
    status = models.CharField(
        max_length=15,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    provider = models.CharField(max_length=100, null=True, blank=True)
    provider_reference = models.CharField(max_length=255, null=True, blank=True)
    provider_response = models.JSONField(default=dict)
    error_message = models.TextField(null=True, blank=True)
    attempt_number = models.IntegerField(default=1)
    attempted_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_delivery_logs'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['notification'], name='idx_delivery_logs_notification'),
            models.Index(fields=['user'], name='idx_delivery_logs_user'),
            models.Index(fields=['channel'], name='idx_delivery_logs_channel'),
            models.Index(fields=['status'], name='idx_delivery_logs_status'),
            models.Index(fields=['attempted_at'], name='idx_delivery_logs_attempted'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(attempt_number__gte=1),
                name='attempt_number_check'
            ),
        ]

    def __str__(self):
        return f"Delivery Log: {self.channel} - {self.status} for {self.user.username}"

    def mark_delivered(self, provider=None, reference=None, response=None):
        """Mark as delivered"""
        from django.utils import timezone
        
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = timezone.now()
        if provider:
            self.provider = provider
        if reference:
            self.provider_reference = reference
        if response:
            self.provider_response = response
        self.save()

    def mark_failed(self, error_message, provider=None, response=None):
        """Mark as failed"""
        self.status = NotificationStatus.FAILED
        self.error_message = error_message
        if provider:
            self.provider = provider
        if response:
            self.provider_response = response
        self.save()

    @classmethod
    def log_attempt(cls, notification, user, channel, status=NotificationStatus.PENDING, **kwargs):
        """Log a delivery attempt"""
        return cls.objects.create(
            notification=notification,
            tenant=notification.tenant,
            user=user,
            channel=channel,
            status=status,
            **kwargs
        )

    @classmethod
    def get_delivery_stats(cls, notification_id=None, user_id=None, days=7):
        """Get delivery statistics"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(created_at__gte=cutoff_date)
        
        if notification_id:
            queryset = queryset.filter(notification_id=notification_id)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        stats = queryset.values('status', 'channel').annotate(count=Count('id'))
        
        return {f"{stat['channel']}_{stat['status']}": stat['count'] for stat in stats}

    @classmethod
    def get_failed_deliveries(cls, channel=None, hours=24):
        """Get failed deliveries for retry"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        queryset = cls.objects.filter(
            status=NotificationStatus.FAILED,
            attempted_at__gte=cutoff_time
        )
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        return queryset.order_by('-attempted_at')

    @classmethod
    def cleanup_old_logs(cls, days=30):
        """Clean up old delivery logs"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return cls.objects.filter(created_at__lte=cutoff_date).delete()[0]
