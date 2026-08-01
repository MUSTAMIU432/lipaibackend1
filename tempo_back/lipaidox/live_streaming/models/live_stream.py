import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class LiveStreamStatus(models.TextChoices):
    """Status of live streams"""
    SCHEDULED = 'scheduled', 'Scheduled'
    LIVE = 'live', 'Live'
    ENDED = 'ended', 'Ended'
    CANCELLED = 'cancelled', 'Cancelled'
    FAILED = 'failed', 'Failed'


class LiveStreamAccessType(models.TextChoices):
    """Access types for live streams"""
    FREE = 'free', 'Free'
    SUBSCRIPTION = 'subscription', 'Subscription'
    PAID_ENTRY = 'paid_entry', 'Paid Entry'


class LiveStream(TenantAwareModel):
    """
    Live streams - Module 13
    Core model for live streaming functionality
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='live_streams'
    )

    # Stream Details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    thumbnail_url = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    tags = models.TextField(blank=True, null=True)  # Stored as JSON array

    # Access
    access_type = models.CharField(
        max_length=20,
        choices=LiveStreamAccessType.choices,
        default=LiveStreamAccessType.FREE
    )
    entry_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=LiveStreamStatus.choices,
        default=LiveStreamStatus.SCHEDULED
    )

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Credits Consumed
    credits_used = models.IntegerField(default=0)
    credit_deduction_interval = models.IntegerField(default=15)  # seconds

    # Stream Technical
    stream_key = models.CharField(max_length=255, blank=True, null=True)
    stream_url = models.TextField(blank=True, null=True)
    playback_url = models.TextField(blank=True, null=True)
    recording_url = models.TextField(blank=True, null=True)
    is_recorded = models.BooleanField(default=False)

    # Viewer Stats
    peak_viewer_count = models.IntegerField(default=0)
    total_viewer_count = models.IntegerField(default=0)
    current_viewer_count = models.IntegerField(default=0)

    # Revenue
    total_tips_amount = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_credits_received = models.IntegerField(default=0)
    total_credits_value = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Chat
    chat_enabled = models.BooleanField(default=True)
    chat_followers_only = models.BooleanField(default=False)
    chat_subscribers_only = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'live_streams'
        app_label = 'lipaidox_live_streaming'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator'], name='idx_livestream_creator'),
            models.Index(fields=['status'], name='idx_livestream_status'),
            models.Index(fields=['access_type'], name='idx_livestream_access'),
            models.Index(fields=['scheduled_at'], name='idx_livestream_scheduled'),
            models.Index(fields=['started_at'], name='idx_livestream_started'),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(access_type=LiveStreamAccessType.PAID_ENTRY) | models.Q(entry_price__isnull=False),
                name='livestream_entry_price_check'
            ),
            models.CheckConstraint(check=models.Q(credits_used__gte=0), name='livestream_credits_used_check'),
            models.CheckConstraint(
                check=models.Q(peak_viewer_count__gte=0) & models.Q(total_viewer_count__gte=0) & models.Q(current_viewer_count__gte=0),
                name='livestream_viewer_count_check'
            ),
            models.CheckConstraint(
                check=models.Q(total_tips_amount__gte=0) & models.Q(total_credits_received__gte=0) & models.Q(total_revenue__gte=0),
                name='livestream_revenue_check'
            ),
            models.CheckConstraint(
                check=models.Q(duration_seconds__isnull=True) | models.Q(duration_seconds__gte=0),
                name='livestream_duration_check'
            ),
        ]

    def __str__(self):
        return f"Live Stream: {self.title} by {self.creator.username}"

    @property
    def tags_list(self):
        """Get tags as Python list"""
        if self.tags:
            import json
            try:
                return json.loads(self.tags)
            except:
                return []
        return []

    @tags_list.setter
    def tags_list(self, value):
        """Set tags from Python list"""
        import json
        self.tags = json.dumps(value) if value else '[]'

    def start_stream(self):
        """Start the live stream"""
        from django.utils import timezone
        self.status = LiveStreamStatus.LIVE
        self.started_at = timezone.now()
        self.save()

    def end_stream(self):
        """End the live stream"""
        from django.utils import timezone
        self.status = LiveStreamStatus.ENDED
        self.ended_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        self.current_viewer_count = 0
        self.save()

    def cancel_stream(self):
        """Cancel the live stream"""
        from django.utils import timezone
        self.status = LiveStreamStatus.CANCELLED
        self.current_viewer_count = 0
        self.save()

    def update_viewer_count(self, current_count):
        """Update viewer statistics"""
        self.current_viewer_count = current_count
        if current_count > self.peak_viewer_count:
            self.peak_viewer_count = current_count
        self.save()

    def add_tip_amount(self, amount):
        """Add tip amount to total revenue"""
        self.total_tips_amount += amount
        self.total_revenue += amount
        self.save()

    def add_credits_received(self, credits, monetary_value):
        """Add credits received to totals"""
        self.total_credits_received += credits
        self.total_credits_value += monetary_value
        self.total_revenue += monetary_value
        self.save()
