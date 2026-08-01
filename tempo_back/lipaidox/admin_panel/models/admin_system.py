import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class SystemAlertType(models.TextChoices):
    ERROR = 'error', 'Error'
    WARNING = 'warning', 'Warning'
    INFO = 'info', 'Info'
    SUCCESS = 'success', 'Success'

class SystemAlert(TenantAwareModel):
    """
    System alerts for admin dashboard
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    type = models.CharField(
        max_length=20,
        choices=SystemAlertType.choices,
        default=SystemAlertType.INFO
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_alerts"
    )
    
    # Metadata
    source = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'payment_system', 'user_registration'
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "admin_system_alerts"
        app_label = "admin_panel"
        indexes = [
            models.Index(fields=['type'], name='idx_alert_type'),
            models.Index(fields=['resolved_at'], name='idx_alert_resolved'),
            models.Index(fields=['-created_at'], name='idx_alert_created'),
        ]
    
    def __str__(self):
        return f"{self.type.title()}: {self.title}"
    
    def resolve(self, resolved_by):
        """Mark alert as resolved"""
        from django.utils import timezone
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.save()

class PlatformSetting(TenantAwareModel):
    """
    Platform-wide settings
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(null=True, blank=True)
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    
    # Validation
    is_required = models.BooleanField(default=False)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    allowed_values = models.JSONField(default=list, blank=True)  # For enum validation
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "admin_platform_settings"
        app_label = "admin_panel"
    
    def __str__(self):
        return f"{self.key} = {self.value}"
    
    def cast_value(self):
        """Cast string value to appropriate data type"""
        if self.data_type == 'integer':
            return int(self.value)
        elif self.data_type == 'float':
            return float(self.value)
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'on')
        elif self.data_type == 'json':
            import json
            return json.loads(self.value)
        return self.value
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get setting value with default"""
        try:
            setting = cls.objects.get(key=key)
            return setting.cast_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value, description=None):
        """Set setting value"""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': str(value),
                'description': description,
            }
        )
        return setting

class AuditLog(TenantAwareModel):
    """
    System audit logs for security and compliance
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs"
    )
    
    action = models.CharField(max_length=100)  # e.g., 'course_created', 'user_suspended'
    resource_type = models.CharField(max_length=50)  # e.g., 'course', 'user', 'payment'
    resource_id = models.UUIDField(null=True, blank=True)
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Change details
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    
    # Result
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "admin_audit_logs"
        app_label = "admin_panel"
        indexes = [
            models.Index(fields=['user'], name='idx_audit_user'),
            models.Index(fields=['action'], name='idx_audit_action'),
            models.Index(fields=['resource_type'], name='idx_audit_resource'),
            models.Index(fields=['-created_at'], name='idx_audit_created'),
        ]
    
    def __str__(self):
        return f"{self.action} by {self.user.username if self.user else 'System'}"

class EmailCampaignStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SCHEDULED = 'scheduled', 'Scheduled'
    SENDING = 'sending', 'Sending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'

class EmailCampaign(TenantAwareModel):
    """
    Email campaign management
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    
    # Targeting
    recipient_count = models.IntegerField(default=0)
    target_roles = models.JSONField(default=list, blank=True)  # ['student', 'instructor', 'admin']
    target_filters = models.JSONField(default=dict, blank=True)  # Additional filtering criteria
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=EmailCampaignStatus.choices,
        default=EmailCampaignStatus.DRAFT
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    unsubscribed_count = models.IntegerField(default=0)
    
    # Created by
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_campaigns"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "admin_email_campaigns"
        app_label = "admin_panel"
        indexes = [
            models.Index(fields=['status'], name='idx_campaign_status'),
            models.Index(fields=['-created_at'], name='idx_campaign_created'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.status})"

class RefundStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    PROCESSING = 'processing', 'Processing'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    COMPLETED = 'completed', 'Completed'

class Refund(TenantAwareModel):
    """
    Refund management
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    payment = models.ForeignKey(
        'lms_financial.LmsPayment',
        on_delete=models.CASCADE,
        related_name="refunds"
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.REQUESTED
    )
    
    # Processed by
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds"
    )
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "admin_refunds"
        app_label = "admin_panel"
        indexes = [
            models.Index(fields=['payment'], name='idx_refund_payment'),
            models.Index(fields=['status'], name='idx_refund_status'),
            models.Index(fields=['-requested_at'], name='idx_refund_requested'),
        ]
    
    def __str__(self):
        return f"Refund {self.amount} for payment {self.payment.id}"

class ContentReportStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    REVIEWING = 'reviewing', 'Reviewing'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'

class ContentReport(TenantAwareModel):
    """
    Content moderation reports
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="filed_reports"
    )
    
    content_type = models.CharField(max_length=50)  # e.g., 'course', 'lesson', 'comment'
    content_id = models.UUIDField()
    
    reason = models.CharField(max_length=100)
    description = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=ContentReportStatus.choices,
        default=ContentReportStatus.PENDING
    )
    
    # Resolution
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports"
    )
    resolution_note = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "admin_content_reports"
        app_label = "admin_panel"
        indexes = [
            models.Index(fields=['content_type', 'content_id'], name='idx_report_content'),
            models.Index(fields=['status'], name='idx_report_status'),
            models.Index(fields=['-created_at'], name='idx_report_created'),
        ]
    
    def __str__(self):
        return f"Report on {self.content_type} by {self.reporter.username}"
