import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import DeliveryChannel, NotificationStatus


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
            models.Index(fields=['notification_type', 'channel'], name='idx_notif_tmpl_type_channel'),
            models.Index(fields=['is_active'], name='idx_notif_tmpl_active'),
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


# NOTE: a second copy of NotificationDeliveryLog used to live here. It duplicated
# the canonical model in notification_delivery_logs.py (same app label, same
# db_table), so importing this module raised Django's conflicting-models error and
# kept the whole notifications GraphQL surface unloadable. Use the canonical one.
