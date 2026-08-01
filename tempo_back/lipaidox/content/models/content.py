import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from multitenant.models import TenantAwareModel
from .series import ContentSeries

class ContentStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'
    FLAGGED = 'flagged', 'Flagged'
    UNDER_REVIEW = 'under_review', 'Under Review'

class ContentAccessType(models.TextChoices):
    FREE = 'free', 'Free'
    ONE_TIME = 'one_time', 'One-Time Payment'
    TIMED = 'timed', 'Timed Payment'
    SUBSCRIPTION = 'subscription', 'Subscription Required'

class ContentFormat(models.TextChoices):
    SINGLE_IMAGE = 'single_image', 'Single Image'
    SINGLE_VIDEO = 'single_video', 'Single Video'
    AUDIO = 'audio', 'Audio'
    BLOG = 'blog', 'Blog'
    LIVE_STREAM = 'live_stream', 'Live Stream'
    GALLERY = 'gallery', 'Gallery / Slideshow'

class Content(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="content")

    # Details
    title = models.CharField(max_length=255)
    description = models.TextField(max_length=2200, null=True, blank=True)
    content_format = models.CharField(max_length=20, choices=ContentFormat.choices, default=ContentFormat.SINGLE_IMAGE)
    # Presentation style for styled Text (blog) posts: { mode, backgroundId, color,
    # fontId, fontSize, align }. Null for ordinary content.
    style = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ContentStatus.choices, default=ContentStatus.DRAFT)

    # Categories
    categories = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    primary_category = models.CharField(max_length=100, null=True, blank=True)

    # Access & Payment
    access_type = models.CharField(max_length=20, choices=ContentAccessType.choices, default=ContentAccessType.FREE)
    one_time_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    timed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    timed_duration_value = models.IntegerField(null=True, blank=True)
    timed_duration_unit = models.CharField(max_length=10, choices=[('hours', 'Hours'), ('days', 'Days')], null=True, blank=True)
    allow_download = models.BooleanField(default=False)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)

    # Series
    is_continuous = models.BooleanField(default=False)
    series = models.ForeignKey(ContentSeries, on_delete=models.SET_NULL, null=True, blank=True, related_name="episodes")
    episode_number = models.IntegerField(null=True, blank=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Engagement Counters (Stored collectively for scale)
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    purchase_count = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0.0000)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content"
        app_label = "lipaidox_content"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['access_type']),
            models.Index(fields=['published_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"