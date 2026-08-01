import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .notification import DeliveryChannel, NotificationStatus


class NotificationTemplate(TenantAwareModel):
    """
    Notification Templates - Module 17
    Reusable templates for different notification types
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=20)
    channel = models.CharField(
        max_length=20,
        choices=DeliveryChannel.choices
    )
    
    # Template content
    subject_template = models.CharField(max_length=255, null=True, blank=True)
    body_template = models.TextField()
    
    # Template variables (JSON schema for validation)
    variables_schema = models.JSONField(default=dict)
    
    # Default settings
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_templates'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['notification_type', 'channel'], name='idx_notification_templates_type_channel'),
            models.Index(fields=['is_active'], name='idx_notification_templates_active'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['notification_type', 'channel'],
                name='notification_templates_unique'
            ),
        ]

    def __str__(self):
        return f"Template: {self.name} - {self.notification_type} - {self.channel}"

    def render(self, context):
        """Render template with context"""
        try:
            # Simple string formatting (in production, use proper template engine)
            subject = self.subject_template
            if subject:
                subject = subject.format(**context)
            
            body = self.body_template.format(**context)
            
            return {
                'subject': subject,
                'body': body
            }
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    @classmethod
    def get_template(cls, notification_type, channel):
        """Get template for notification type and channel"""
        try:
            return cls.objects.get(
                notification_type=notification_type,
                channel=channel,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_default_templates(cls, tenant):
        """Create default notification templates"""
        templates = [
            # Email templates
            {
                'name': 'New Subscriber Email',
                'notification_type': 'new_subscriber',
                'channel': 'email',
                'subject_template': 'New Subscriber: {subscriber_name}',
                'body_template': 'Hi {creator_name},\n\nYou have a new subscriber: {subscriber_name}!\n\nThey subscribed to your {plan_name} plan.\n\nBest regards,\nLipaidox Team',
                'variables_schema': {'subscriber_name': 'string', 'creator_name': 'string', 'plan_name': 'string'}
            },
            {
                'name': 'New Tip Email',
                'notification_type': 'new_tip',
                'channel': 'email',
                'subject_template': 'You received a tip!',
                'body_template': 'Hi {creator_name},\n\nYou received a tip of ${amount} from {sender_name}!\n\nMessage: {message}\n\nThank you for your great content!\n\nLipaidox Team',
                'variables_schema': {'creator_name': 'string', 'amount': 'number', 'sender_name': 'string', 'message': 'string'}
            },
            # Push notification templates
            {
                'name': 'New Content Push',
                'notification_type': 'new_content',
                'channel': 'push',
                'subject_template': None,
                'body_template': '{creator_name} posted new content: {content_title}',
                'variables_schema': {'creator_name': 'string', 'content_title': 'string'}
            },
            # SMS templates
            {
                'name': 'Security Alert SMS',
                'notification_type': 'security_alert',
                'channel': 'sms',
                'subject_template': None,
                'body_template': 'Lipaidox: {message}. If this wasn\'t you, please secure your account immediately.',
                'variables_schema': {'message': 'string'}
            },
        ]
        
        created_templates = []
        for template_data in templates:
            template = cls.objects.create(
                tenant=tenant,
                **template_data
            )
            created_templates.append(template)
        
        return created_templates


class NotificationDeliveryLog(TenantAwareModel):
    """
    Notification Delivery Log - Module 17
    Log of all notification delivery attempts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        'Notification',
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )
    queue_entry = models.ForeignKey(
        'NotificationQueue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delivery_logs'
    )
    channel = models.CharField(
        max_length=20,
        choices=DeliveryChannel.choices
    )
    recipient_address = models.CharField(max_length=255)
    
    # Delivery details
    status = models.CharField(
        max_length=15,
        choices=NotificationStatus.choices
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    response_data = models.JSONField(default=dict)
    
    # Provider information
    provider = models.CharField(max_length=50, null=True, blank=True)
    external_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification_delivery_log'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['notification'], name='idx_delivery_log_notification'),
            models.Index(fields=['channel'], name='idx_delivery_log_channel'),
            models.Index(fields=['status'], name='idx_delivery_log_status'),
            models.Index(fields=['created_at'], name='idx_delivery_log_created'),
        ]

    def __str__(self):
        return f"Delivery Log: {self.channel} - {self.status}"

    @classmethod
    def log_delivery(cls, notification, channel, recipient_address, status, **kwargs):
        """Log a delivery attempt"""
        return cls.objects.create(
            notification=notification,
            tenant=notification.tenant,
            channel=channel,
            recipient_address=recipient_address,
            status=status,
            **kwargs
        )

    @classmethod
    def get_delivery_stats(cls, notification_id=None, days=7):
        """Get delivery statistics"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(created_at__gte=cutoff_date)
        
        if notification_id:
            queryset = queryset.filter(notification_id=notification_id)
        
        stats = queryset.values('status', 'channel').annotate(count=Count('id'))
        
        return {f"{stat['channel']}_{stat['status']}": stat['count'] for stat in stats}
