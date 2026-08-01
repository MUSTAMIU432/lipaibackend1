import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import DeviceType, SessionStatus


class DeviceSession(TenantAwareModel):
    """
    Device Sessions - Module 16
    Track user device sessions and trust status
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='device_sessions'
    )
    refresh_token = models.ForeignKey(
        'lipaidox_auth.RefreshToken',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device_session'
    )

    # Device Detail
    device_fingerprint = models.CharField(max_length=255)
    device_name = models.CharField(max_length=255, null=True, blank=True)
    device_type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN
    )
    browser = models.CharField(max_length=100, null=True, blank=True)
    os = models.CharField(max_length=100, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Location
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)

    # Trust
    is_trusted = models.BooleanField(default=False)
    trusted_at = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=10,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE
    )
    last_active_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_sessions'
        app_label = 'lipaidox_security'
        indexes = [
            models.Index(fields=['user'], name='idx_device_sessions_user'),
            models.Index(fields=['device_fingerprint'], name='idx_device_sessions_fp'),
            models.Index(fields=['status'], name='idx_device_sessions_status'),
            models.Index(fields=['is_trusted'], name='idx_device_sessions_trusted'),
            models.Index(fields=['last_active_at'], name='idx_device_sessions_last'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_fingerprint'],
                name='device_sessions_fingerprint_user_unique'
            ),
        ]

    def __str__(self):
        return f"Device Session: {self.user.username} - {self.device_name or 'Unknown'}"

    def is_expired(self):
        """Check if session is expired"""
        from django.utils import timezone
        return self.expires_at <= timezone.now()

    def is_active(self):
        """Check if session is active"""
        return (
            self.status == SessionStatus.ACTIVE and
            not self.is_expired()
        )

    def trust_device(self):
        """Mark device as trusted"""
        from django.utils import timezone
        
        self.is_trusted = True
        self.trusted_at = timezone.now()
        self.save()

    def revoke_session(self, reason=None):
        """Revoke the session"""
        from django.utils import timezone
        
        self.status = SessionStatus.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.save()

    def expire_session(self):
        """Mark session as expired"""
        self.status = SessionStatus.EXPIRED
        self.save()

    @classmethod
    def create_session(cls, user, device_fingerprint, expires_hours=24, **kwargs):
        """Create a new device session"""
        from django.utils import timezone
        from datetime import timedelta
        
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            device_fingerprint=device_fingerprint,
            expires_at=timezone.now() + timedelta(hours=expires_hours),
            **kwargs
        )

    @classmethod
    def get_user_sessions(cls, user, active_only=True):
        """Get user's device sessions"""
        queryset = cls.objects.filter(user=user)
        
        if active_only:
            queryset = queryset.filter(status=SessionStatus.ACTIVE)
        
        return queryset.order_by('-last_active_at')

    @classmethod
    def get_trusted_devices(cls, user):
        """Get user's trusted devices"""
        return cls.objects.filter(
            user=user,
            is_trusted=True,
            status=SessionStatus.ACTIVE
        )

    @classmethod
    def cleanup_expired_sessions(cls):
        """Clean up expired sessions"""
        from django.utils import timezone
        
        expired_sessions = cls.objects.filter(
            expires_at__lte=timezone.now(),
            status=SessionStatus.ACTIVE
        )
        
        count = 0
        for session in expired_sessions:
            session.expire_session()
            count += 1
        
        return count

    @classmethod
    def revoke_all_user_sessions(cls, user, except_session=None):
        """Revoke all sessions for a user"""
        queryset = cls.objects.filter(
            user=user,
            status=SessionStatus.ACTIVE
        )
        
        if except_session:
            queryset = queryset.exclude(id=except_session.id)
        
        count = 0
        for session in queryset:
            session.revoke_session('All sessions revoked')
            count += 1
        
        return count
