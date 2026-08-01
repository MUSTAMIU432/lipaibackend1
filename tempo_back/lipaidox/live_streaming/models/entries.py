import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class LiveStreamEntry(TenantAwareModel):
    """
    Records that a fan paid the entry fee for a paid_entry live stream. One row
    per (stream, fan) so rejoining the same stream is free after the first pay.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        'lipaidox_live_streaming.LiveStream',
        on_delete=models.CASCADE,
        related_name='entries',
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_entries',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'live_stream_entries'
        app_label = 'lipaidox_live_streaming'
        constraints = [
            models.UniqueConstraint(
                fields=['live_stream', 'fan'], name='live_stream_entry_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['fan'], name='idx_lse_fan'),
            models.Index(fields=['live_stream'], name='idx_lse_stream'),
        ]

    def __str__(self):
        return f"Entry: {self.fan_id} -> {self.live_stream_id} ({self.amount})"
