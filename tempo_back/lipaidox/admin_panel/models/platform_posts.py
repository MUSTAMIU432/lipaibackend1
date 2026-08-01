import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PlatformPostType(models.TextChoices):
    """Types of platform posts"""
    ANNOUNCEMENT = 'announcement', 'Announcement'
    TUTORIAL = 'tutorial', 'Tutorial'
    FEATURE_GUIDE = 'feature_guide', 'Feature Guide'
    PROMOTIONAL = 'promotional', 'Promotional'
    MAINTENANCE_NOTICE = 'maintenance_notice', 'Maintenance Notice'
    POLICY_UPDATE = 'policy_update', 'Policy Update'


class PlatformPost(TenantAwareModel):
    """
    Platform posts - feed posts from official platform accounts
    Reuses the content table for the actual content
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.OneToOneField(
        "lipaidox_content.Content",
        on_delete=models.CASCADE,
        related_name="platform_post"
    )
    platform_account = models.ForeignKey(
        "PlatformAccount",
        on_delete=models.CASCADE,
        related_name="posts"
    )
    announcement = models.ForeignKey(
        "Announcement",
        on_delete=models.SET_NULL,
        related_name="platform_posts",
        null=True,
        blank=True
    )
    created_by_admin = models.ForeignKey(
        "AdminAccount",
        on_delete=models.CASCADE,
        related_name="created_platform_posts"
    )

    # Post type
    post_type = models.CharField(max_length=30, choices=PlatformPostType.choices, default=PlatformPostType.ANNOUNCEMENT)

    # Targeting
    target_audience = models.CharField(max_length=30, choices=[
        ('all_users', 'All Users'),
        ('creators_only', 'Creators Only'),
        ('fans_only', 'Fans Only'),
        ('premium_creators', 'Premium Creators'),
        ('promax_creators', 'Promax Creators'),
        ('verified_creators', 'Verified Creators'),
        ('specific_users', 'Specific Users'),
    ], default='all_users')
    target_user_ids = models.JSONField(default=list, blank=True)
    is_pinned = models.BooleanField(default=False)
    is_system_post = models.BooleanField(default=True)

    # Engagement flags
    allow_comments = models.BooleanField(default=False)
    allow_likes = models.BooleanField(default=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_posts"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['platform_account']),
            models.Index(fields=['post_type']),
            models.Index(fields=['target_audience']),
            models.Index(fields=['is_pinned']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Platform Post: {self.content.title} by @{self.platform_account.handle}"
