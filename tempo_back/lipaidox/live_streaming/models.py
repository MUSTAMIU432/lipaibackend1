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


class ViewerStatus(models.TextChoices):
    """Status of viewers in live streams"""
    WATCHING = 'watching', 'Watching'
    LEFT = 'left', 'Left'
    KICKED = 'kicked', 'Kicked'
    BANNED = 'banned', 'Banned'


class ChatMessageStatus(models.TextChoices):
    """Status of chat messages"""
    VISIBLE = 'visible', 'Visible'
    DELETED = 'deleted', 'Deleted'
    FLAGGED = 'flagged', 'Flagged'
    AUTO_MODERATED = 'auto_moderated', 'Auto Moderated'


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
                check=models.Q(access_type__ne=LiveStreamAccessType.PAID_ENTRY) | models.Q(entry_price__isnull=False),
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


class LiveStreamViewer(TenantAwareModel):
    """
    Tracks every fan who joined a live stream
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        LiveStream,
        on_delete=models.CASCADE,
        related_name='viewers'
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_views'
    )
    status = models.CharField(
        max_length=20,
        choices=ViewerStatus.choices,
        default=ViewerStatus.WATCHING
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    watch_duration_s = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    is_subscriber = models.BooleanField(default=False)
    credits_sent = models.IntegerField(default=0)
    tips_sent = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'live_stream_viewers'
        app_label = 'lipaidox_live_streaming'
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['live_stream'], name='idx_viewer_stream'),
            models.Index(fields=['fan'], name='idx_viewer_fan'),
            models.Index(fields=['status'], name='idx_viewer_status'),
            models.Index(fields=['joined_at'], name='idx_viewer_joined'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['live_stream', 'fan'],
                name='livestream_viewers_unique'
            ),
            models.CheckConstraint(
                check=models.Q(watch_duration_s__isnull=True) | models.Q(watch_duration_s__gte=0),
                name='viewer_watch_duration_check'
            ),
            models.CheckConstraint(check=models.Q(credits_sent__gte=0), name='viewer_credits_sent_check'),
            models.CheckConstraint(check=models.Q(tips_sent__gte=0), name='viewer_tips_sent_check'),
        ]

    def __str__(self):
        return f"Viewer: {self.fan.username} in {self.live_stream.title}"

    def leave_stream(self):
        """Mark viewer as left"""
        from django.utils import timezone
        self.status = ViewerStatus.LEFT
        self.left_at = timezone.now()
        if self.joined_at:
            self.watch_duration_s = int((self.left_at - self.joined_at).total_seconds())
        self.save()

    def add_credits_sent(self, credits):
        """Add credits sent by this viewer"""
        self.credits_sent += credits
        self.save()

    def add_tip_sent(self, amount):
        """Add tip amount sent by this viewer"""
        self.tips_sent += amount
        self.save()


class LiveStreamChatMessage(TenantAwareModel):
    """
    Every message sent in the live stream chat
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        LiveStream,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_chat_messages'
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ChatMessageStatus.choices,
        default=ChatMessageStatus.VISIBLE
    )
    is_pinned = models.BooleanField(default=False)
    is_creator_message = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_chat_messages'
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'live_stream_chat_messages'
        app_label = 'lipaidox_live_streaming'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['live_stream'], name='idx_chat_stream'),
            models.Index(fields=['fan'], name='idx_chat_fan'),
            models.Index(fields=['status'], name='idx_chat_status'),
            models.Index(fields=['sent_at'], name='idx_chat_sent'),
        ]
        constraints = []

    def __str__(self):
        return f"Chat: {self.fan.username} in {self.live_stream.title}"

    def delete_message(self, deleted_by_user):
        """Delete a chat message"""
        from django.utils import timezone
        self.status = ChatMessageStatus.DELETED
        self.deleted_by = deleted_by_user
        self.deleted_at = timezone.now()
        self.save()

    def pin_message(self):
        """Pin a chat message"""
        self.is_pinned = True
        self.save()

    def unpin_message(self):
        """Unpin a chat message"""
        self.is_pinned = False
        self.save()


class LiveStreamCreditTransaction(TenantAwareModel):
    """
    Every credit gift received by the creator during a specific live stream
    Links Module 13 back to Module 22 (fan credit gifts)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        LiveStream,
        on_delete=models.CASCADE,
        related_name='credit_transactions'
    )
    gift = models.ForeignKey(
        'lipaidox_credits.FanCreditGiftSent',
        on_delete=models.CASCADE,
        related_name='live_stream_transactions'
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_credit_transactions'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='live_stream_credit_transactions'
    )
    credits_received = models.IntegerField()
    monetary_value = models.DecimalField(max_digits=10, decimal_places=4)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=4)
    creator_earnings = models.DecimalField(max_digits=10, decimal_places=4)
    animation_type = models.CharField(
        max_length=50,
        choices=[('heart', 'Heart'), ('rose', 'Rose'), ('diamond', 'Diamond')],
        default='heart'
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'live_stream_credit_transactions'
        app_label = 'lipaidox_live_streaming'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['live_stream'], name='idx_stream_credit_stream'),
            models.Index(fields=['fan'], name='idx_stream_credit_fan'),
            models.Index(fields=['creator'], name='idx_stream_credit_creator'),
            models.Index(fields=['received_at'], name='idx_stream_credit_received'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_received__gt=0), name='stream_credits_received_check'),
            models.CheckConstraint(check=models.Q(creator_earnings__gte=0), name='stream_creator_earnings_check'),
        ]

    def __str__(self):
        return f"Credit Transaction: {self.credits_received} credits from {self.fan.username} to {self.creator.username}"
