import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .notification import DeliveryChannel, NotificationStatus


class NotificationQueue(TenantAwareModel):
    """
    Notification Queue - Module 17
    Queue for external notification delivery (email, SMS, push)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        'Notification',
        on_delete=models.CASCADE,
        related_name='queue_entries'
    )
    channel = models.CharField(
        max_length=20,
        choices=DeliveryChannel.choices
    )
    recipient_address = models.EmailField()  # Email or phone number
    subject = models.CharField(max_length=255)
    content = models.TextField()
    template_name = models.CharField(max_length=100, null=True, blank=True)
    template_data = models.JSONField(default=dict)
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_queue'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['status'], name='idx_notification_queue_status'),
            models.Index(fields=['channel'], name='idx_notification_queue_channel'),
            models.Index(fields=['scheduled_at'], name='idx_notification_queue_scheduled'),
            models.Index(fields=['priority', 'status'], name='idx_notification_queue_priority_status'),
            models.Index(fields=['created_at'], name='idx_notification_queue_created'),
        ]

    def __str__(self):
        return f"Queue: {self.channel} - {self.recipient_address} - {self.status}"

    def can_retry(self):
        """Check if notification can be retried"""
        return (
            self.status == NotificationStatus.FAILED and
            self.attempts < self.max_attempts
        )

    def mark_sent(self):
        """Mark notification as sent"""
        from django.utils import timezone
        
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        self.save()

    def mark_delivered(self):
        """Mark notification as delivered"""
        from django.utils import timezone
        
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save()

    def mark_failed(self, error_message):
        """Mark notification as failed"""
        from django.utils import timezone
        
        self.status = NotificationStatus.FAILED
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.error_message = error_message
        self.save()

    def is_ready_to_send(self):
        """Check if notification is ready to be sent"""
        from django.utils import timezone
        
        return (
            self.status == NotificationStatus.PENDING and
            (self.scheduled_at is None or self.scheduled_at <= timezone.now())
        )

    @classmethod
    def queue_notification(cls, notification, channel, recipient_address, **kwargs):
        """Queue a notification for delivery"""
        return cls.objects.create(
            notification=notification,
            tenant=notification.tenant,
            channel=channel,
            recipient_address=recipient_address,
            **kwargs
        )

    @classmethod
    def get_pending_notifications(cls, channel=None, limit=100):
        """Get pending notifications ready to send"""
        from django.utils import timezone
        
        queryset = cls.objects.filter(
            status=NotificationStatus.PENDING
        ).filter(
            models.Q(scheduled_at__isnull=True) | models.Q(scheduled_at__lte=timezone.now())
        )
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        return queryset.order_by('-priority', 'created_at')[:limit]

    @classmethod
    def get_failed_notifications(cls, channel=None, retryable_only=True):
        """Get failed notifications for retry"""
        queryset = cls.objects.filter(status=NotificationStatus.FAILED)
        
        if retryable_only:
            queryset = queryset.filter(attempts__lt=models.F('max_attempts'))
        
        if channel:
            queryset = queryset.filter(channel=channel)
        
        return queryset.order_by('-priority', 'last_attempt_at')

    @classmethod
    def cleanup_old_notifications(cls, days=30):
        """Clean up old delivered/failed notifications"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return cls.objects.filter(
            status__in=[NotificationStatus.DELIVERED, NotificationStatus.FAILED],
            created_at__lte=cutoff_date
        ).delete()[0]

    @classmethod
    def get_delivery_stats(cls, days=7):
        """Get delivery statistics"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        stats = cls.objects.filter(
            created_at__gte=cutoff_date
        ).values('status', 'channel').annotate(count=Count('id'))
        
        return {f"{stat['channel']}_{stat['status']}": stat['count'] for stat in stats}
