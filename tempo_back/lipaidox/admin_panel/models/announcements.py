import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class AnnouncementType(models.TextChoices):
    """Types of announcements"""
    PLATFORM_UPDATE = 'platform_update', 'Platform Update'
    FEATURE_RELEASE = 'feature_release', 'Feature Release'
    MAINTENANCE = 'maintenance', 'Maintenance'
    POLICY_CHANGE = 'policy_change', 'Policy Change'
    PROMOTION = 'promotion', 'Promotion'
    SECURITY_ALERT = 'security_alert', 'Security Alert'
    GENERAL = 'general', 'General'


class AnnouncementTarget(models.TextChoices):
    """Target audiences for announcements"""
    ALL_USERS = 'all_users', 'All Users'
    CREATORS_ONLY = 'creators_only', 'Creators Only'
    FANS_ONLY = 'fans_only', 'Fans Only'
    PREMIUM_CREATORS = 'premium_creators', 'Premium Creators'
    PROMAX_CREATORS = 'promax_creators', 'Promax Creators'
    VERIFIED_CREATORS = 'verified_creators', 'Verified Creators'
    SPECIFIC_USERS = 'specific_users', 'Specific Users'


class AnnouncementStatus(models.TextChoices):
    """Status of announcements"""
    DRAFT = 'draft', 'Draft'
    SCHEDULED = 'scheduled', 'Scheduled'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'


class Announcement(TenantAwareModel):
    """
    Platform announcements with targeting and scheduling
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform_account = models.ForeignKey(
        "PlatformAccount",
        on_delete=models.CASCADE,
        related_name="announcements"
    )
    created_by_admin = models.ForeignKey(
        "AdminAccount",
        on_delete=models.CASCADE,
        related_name="created_announcements"
    )

    # Content
    title = models.CharField(max_length=255)
    body = models.TextField()
    announcement_type = models.CharField(max_length=30, choices=AnnouncementType.choices, default=AnnouncementType.GENERAL)
    banner_image_url = models.URLField(max_length=2000, blank=True, null=True)
    cta_label = models.CharField(max_length=100, blank=True, null=True)
    cta_url = models.URLField(max_length=2000, blank=True, null=True)

    # Targeting
    target_audience = models.CharField(max_length=30, choices=AnnouncementTarget.choices, default=AnnouncementTarget.ALL_USERS)
    target_user_ids = models.JSONField(default=list, blank=True)

    # Status & Scheduling
    status = models.CharField(max_length=20, choices=AnnouncementStatus.choices, default=AnnouncementStatus.DRAFT)
    is_pinned = models.BooleanField(default=False)
    show_as_banner = models.BooleanField(default=False)
    show_in_feed = models.BooleanField(default=True)
    show_as_notification = models.BooleanField(default=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Engagement
    read_count = models.IntegerField(default=0)
    dismissed_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcements"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['platform_account']),
            models.Index(fields=['announcement_type']),
            models.Index(fields=['status']),
            models.Index(fields=['target_audience']),
            models.Index(fields=['published_at']),
            models.Index(fields=['is_pinned']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(read_count__gte=0),
                name='read_count_check'
            ),
            models.CheckConstraint(
                check=models.Q(dismissed_count__gte=0),
                name='dismissed_count_check'
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"


class AnnouncementRead(TenantAwareModel):
    """
    Track which users have read/dismissed announcements
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(
        "Announcement",
        on_delete=models.CASCADE,
        related_name="reads"
    )
    user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="announcement_reads"
    )
    is_dismissed = models.BooleanField(default=False)
    read_at = models.DateTimeField(auto_now_add=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "announcement_reads"
        app_label = "lipaidox_admin_panel"
        unique_together = ['announcement', 'user']
        indexes = [
            models.Index(fields=['announcement']),
            models.Index(fields=['user']),
            models.Index(fields=['is_dismissed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.announcement.title}"
