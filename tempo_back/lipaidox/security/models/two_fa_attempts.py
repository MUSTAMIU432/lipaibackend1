import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import TwoFAMethod, TwoFAAttemptResult


class TwoFAAttempt(TenantAwareModel):
    """
    Two Factor Authentication Attempts - Module 16
    Track every 2FA code attempt for rate limiting and abuse detection
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='two_fa_attempts'
    )
    method = models.CharField(
        max_length=20,
        choices=TwoFAMethod.choices
    )
    code_hash = models.CharField(max_length=255)
    result = models.CharField(
        max_length=15,
        choices=TwoFAAttemptResult.choices,
        default=TwoFAAttemptResult.FAILED
    )
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'two_fa_attempts'
        app_label = 'lipaidox_security'
        indexes = [
            models.Index(fields=['user'], name='idx_two_fa_attempts_user'),
            models.Index(fields=['result'], name='idx_two_fa_attempts_result'),
            models.Index(fields=['created_at'], name='idx_two_fa_attempts_created'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code_hash'],
                name='two_fa_attempts_code_unique'
            ),
        ]

    def __str__(self):
        return f"2FA Attempt: {self.user.username} - {self.method} - {self.result}"

    def is_expired(self):
        """Check if attempt is expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def mark_used(self):
        """Mark attempt as used"""
        from django.utils import timezone
        
        self.result = TwoFAAttemptResult.ALREADY_USED
        self.used_at = timezone.now()
        self.save()

    def mark_success(self):
        """Mark attempt as successful"""
        from django.utils import timezone
        
        self.result = TwoFAAttemptResult.SUCCESS
        self.used_at = timezone.now()
        self.save()

    @classmethod
    def create_attempt(cls, user, method, code_hash, expires_minutes=10, **kwargs):
        """Create a new 2FA attempt"""
        from django.utils import timezone
        from datetime import timedelta
        
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            method=method,
            code_hash=code_hash,
            expires_at=timezone.now() + timedelta(minutes=expires_minutes),
            **kwargs
        )

    @classmethod
    def get_user_attempts(cls, user, hours=24):
        """Get user's 2FA attempts in last N hours"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        return cls.objects.filter(
            user=user,
            created_at__gte=cutoff_time
        ).order_by('-created_at')

    @classmethod
    def get_failed_attempts(cls, user, hours=1):
        """Get failed 2FA attempts in last N hours"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        return cls.objects.filter(
            user=user,
            created_at__gte=cutoff_time,
            result=TwoFAAttemptResult.FAILED
        )

    @classmethod
    def cleanup_expired_attempts(cls):
        """Clean up expired attempts"""
        from django.utils import timezone
        
        expired_attempts = cls.objects.filter(
            expires_at__lte=timezone.now(),
            result=TwoFAAttemptResult.FAILED
        )
        
        return expired_attempts.delete()[0]

    @classmethod
    def is_rate_limited(cls, user, max_attempts=5, hours=1):
        """Check if user is rate limited for 2FA attempts"""
        failed_attempts = cls.get_failed_attempts(user, hours)
        return failed_attempts.count() >= max_attempts
