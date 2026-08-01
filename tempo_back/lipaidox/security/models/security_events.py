import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import SecurityEventType


class SecurityEvent(TenantAwareModel):
    """
    Security Events - Module 16
    Full audit log of all security-related events
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='security_events'
    )
    event_type = models.CharField(
        max_length=30,
        choices=SecurityEventType.choices
    )
    description = models.TextField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    device_fingerprint = models.CharField(max_length=255, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    risk_score_before = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )
    risk_score_after = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'security_events'
        app_label = 'lipaidox_security'
        indexes = [
            models.Index(fields=['user'], name='idx_security_events_user'),
            models.Index(fields=['event_type'], name='idx_security_events_type'),
            models.Index(fields=['created_at'], name='idx_security_events_created'),
        ]

    def __str__(self):
        return f"Security Event: {self.user.username} - {self.event_type}"

    @classmethod
    def create_event(cls, user, event_type, description=None, **kwargs):
        """Create a security event"""
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            event_type=event_type,
            description=description,
            **kwargs
        )

    @classmethod
    def log_login_event(cls, user, success, ip_address=None, **kwargs):
        """Log a login event"""
        event_type = SecurityEventType.LOGIN_SUCCESS if success else SecurityEventType.LOGIN_FAILED
        return cls.create_event(
            user=user,
            event_type=event_type,
            ip_address=ip_address,
            **kwargs
        )

    @classmethod
    def log_2fa_event(cls, user, success, method=None, **kwargs):
        """Log a 2FA event"""
        event_type = SecurityEventType.TWO_FA_ENABLED if success else SecurityEventType.TWO_FA_FAILED
        return cls.create_event(
            user=user,
            event_type=event_type,
            metadata={'method': method} if method else {},
            **kwargs
        )

    @classmethod
    def log_device_event(cls, user, event_type, device_fingerprint=None, **kwargs):
        """Log a device-related event"""
        return cls.create_event(
            user=user,
            event_type=event_type,
            device_fingerprint=device_fingerprint,
            **kwargs
        )

    @classmethod
    def log_account_event(cls, user, event_type, **kwargs):
        """Log an account-level event"""
        return cls.create_event(
            user=user,
            event_type=event_type,
            **kwargs
        )

    @classmethod
    def get_user_events(cls, user, days=30, event_type=None):
        """Get user's security events"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(
            user=user,
            created_at__gte=cutoff_date
        )
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        return queryset.order_by('-created_at')

    @classmethod
    def get_suspicious_events(cls, days=7):
        """Get suspicious security events"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        suspicious_types = [
            SecurityEventType.LOGIN_FAILED,
            SecurityEventType.TWO_FA_FAILED,
            SecurityEventType.SUSPICIOUS_LOGIN,
            SecurityEventType.ACCOUNT_LOCKED,
            SecurityEventType.SESSION_REVOKED
        ]
        
        return cls.objects.filter(
            event_type__in=suspicious_types,
            created_at__gte=cutoff_date
        ).order_by('-created_at')

    @classmethod
    def get_security_summary(cls, user, days=30):
        """Get security summary for user"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        events = cls.objects.filter(
            user=user,
            created_at__gte=cutoff_date
        )
        
        summary = events.values('event_type').annotate(count=Count('id'))
        
        return {event['event_type']: event['count'] for event in summary}
