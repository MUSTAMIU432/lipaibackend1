import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PushPlatform(models.TextChoices):
    """Push notification platforms"""
    FCM = 'fcm', 'Firebase Cloud Messaging'
    APNS = 'apns', 'Apple Push Notification Service'
    WEB_PUSH = 'web_push', 'Web Push'
    EXPO = 'expo', 'Expo Push Service'


class PushToken(TenantAwareModel):
    """
    Push Tokens - Module 17
    Device push notification tokens per user
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='push_tokens'
    )
    device = models.ForeignKey(
        'lipaidox_security.DeviceSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='push_tokens'
    )
    platform = models.CharField(
        max_length=10,
        choices=PushPlatform.choices
    )
    token = models.TextField()
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'push_tokens'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['user'], name='idx_push_tokens_user_id'),
            models.Index(fields=['platform'], name='idx_push_tokens_platform'),
            models.Index(fields=['is_active'], name='idx_push_tokens_is_active'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['token'], name='push_tokens_token_unique'),
        ]

    def __str__(self):
        return f"Push Token: {self.user.username} - {self.platform}"

    def mark_used(self):
        """Mark token as recently used"""
        from django.utils import timezone
        
        self.last_used_at = timezone.now()
        self.save()

    def deactivate(self):
        """Deactivate token"""
        self.is_active = False
        self.save()

    @classmethod
    def register_token(cls, user, token, platform, device=None):
        """Register a new push token"""
        # Check if token already exists
        existing_token = cls.objects.filter(token=token).first()
        if existing_token:
            # Update existing token
            existing_token.user = user
            existing_token.tenant = user.tenant
            existing_token.platform = platform
            existing_token.device = device
            existing_token.is_active = True
            existing_token.save()
            return existing_token
        else:
            # Create new token
            return cls.objects.create(
                user=user,
                tenant=user.tenant,
                token=token,
                platform=platform,
                device=device
            )

    @classmethod
    def get_user_tokens(cls, user, platform=None, active_only=True):
        """Get user's push tokens"""
        queryset = cls.objects.filter(user=user)
        
        if platform:
            queryset = queryset.filter(platform=platform)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('-last_used_at', '-created_at')

    @classmethod
    def cleanup_inactive_tokens(cls, days=90):
        """Clean up inactive tokens"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return cls.objects.filter(
            is_active=False,
            updated_at__lte=cutoff_date
        ).delete()[0]

    @classmethod
    def get_platform_stats(cls):
        """Get platform usage statistics"""
        from django.db.models import Count
        
        return cls.objects.values('platform').annotate(
            total=Count('id'),
            active=Count('id', filter=models.Q(is_active=True))
        )
