import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PlatformAccountType(models.TextChoices):
    """Types of platform accounts"""
    OFFICIAL = 'official', 'Official'
    UPDATES = 'updates', 'Updates'
    SUPPORT = 'support', 'Support'
    MODERATION = 'moderation', 'Moderation'
    PROMOTIONS = 'promotions', 'Promotions'


class PlatformAccount(TenantAwareModel):
    """
    Platform accounts - official system accounts for announcements and posts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="platform_account"
    )
    account_type = models.CharField(max_length=20, choices=PlatformAccountType.choices, default=PlatformAccountType.OFFICIAL)
    handle = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    avatar_url = models.URLField(max_length=2000, blank=True, null=True)
    cover_url = models.URLField(max_length=2000, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=True)
    managed_by = models.ForeignKey(
        "AdminAccount",
        on_delete=models.SET_NULL,
        related_name="managed_platform_accounts",
        null=True,
        blank=True
    )
    follower_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_accounts"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['handle']),
            models.Index(fields=['account_type']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(follower_count__gte=0),
                name='follower_count_check'
            ),
        ]

    def __str__(self):
        return f"@{self.handle} ({self.account_type})"
