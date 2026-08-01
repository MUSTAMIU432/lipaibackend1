import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import LoginResult, DeviceType, TwoFAMethod


class LoginHistory(TenantAwareModel):
    """
    Login History - Module 16
    Track all login attempts for security monitoring
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='login_history'
    )
    result = models.CharField(
        max_length=20,
        choices=LoginResult.choices
    )
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    device_type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN
    )
    device_name = models.CharField(max_length=255, null=True, blank=True)
    browser = models.CharField(max_length=100, null=True, blank=True)
    os = models.CharField(max_length=100, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_id = models.UUIDField(null=True, blank=True)
    two_fa_used = models.BooleanField(default=False)
    two_fa_method = models.CharField(
        max_length=20,
        choices=TwoFAMethod.choices,
        null=True,
        blank=True
    )
    failure_reason = models.TextField(null=True, blank=True)
    is_suspicious = models.BooleanField(default=False)
    suspicious_reason = models.TextField(null=True, blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'login_history'
        app_label = 'lipaidox_security'
        indexes = [
            models.Index(fields=['user'], name='idx_login_history_user'),
            models.Index(fields=['result'], name='idx_login_history_result'),
            models.Index(fields=['ip_address'], name='idx_login_history_ip'),
            models.Index(fields=['is_suspicious'], name='idx_login_history_suspicious'),
            models.Index(fields=['logged_at'], name='idx_login_history_logged'),
        ]

    def __str__(self):
        return f"Login: {self.user.username} - {self.result} at {self.logged_at}"

    @classmethod
    def record_login(cls, user, result, **kwargs):
        """Record a login attempt"""
        from django.utils import timezone
        
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            result=result,
            logged_at=timezone.now(),
            **kwargs
        )

    @classmethod
    def get_user_login_attempts(cls, user, days=30):
        """Get user's login attempts in last N days"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return cls.objects.filter(
            user=user,
            logged_at__gte=cutoff_date
        ).order_by('-logged_at')

    @classmethod
    def get_failed_attempts(cls, user, hours=24):
        """Get failed login attempts in last N hours"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        return cls.objects.filter(
            user=user,
            logged_at__gte=cutoff_time,
            result__in=[
                LoginResult.FAILED_PASSWORD,
                LoginResult.FAILED_2FA,
                LoginResult.FAILED_LOCKED,
                LoginResult.FAILED_SUSPENDED,
                LoginResult.FAILED_UNVERIFIED
            ]
        )

    @classmethod
    def get_suspicious_logins(cls, user=None, days=7):
        """Get suspicious login attempts"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(
            is_suspicious=True,
            logged_at__gte=cutoff_date
        )
        
        if user:
            queryset = queryset.filter(user=user)
        
        return queryset.order_by('-logged_at')

    @classmethod
    def get_login_statistics(cls, user=None, days=30):
        """Get login statistics"""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = cls.objects.filter(logged_at__gte=cutoff_date)
        
        if user:
            queryset = queryset.filter(user=user)
        
        stats = queryset.values('result').annotate(count=Count('id'))
        
        return {stat['result']: stat['count'] for stat in stats}
