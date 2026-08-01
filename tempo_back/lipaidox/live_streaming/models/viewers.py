import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ViewerStatus(models.TextChoices):
    """Status of viewers in live streams"""
    WATCHING = 'watching', 'Watching'
    LEFT = 'left', 'Left'
    KICKED = 'kicked', 'Kicked'
    BANNED = 'banned', 'Banned'


class LiveStreamViewer(TenantAwareModel):
    """
    Tracks every fan who joined a live stream
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        'lipaidox_live_streaming.LiveStream',
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
