import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class LiveStreamCreditTransaction(TenantAwareModel):
    """
    Every credit gift received by the creator during a specific live stream
    Links Module 13 back to Module 22 (fan credit gifts)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        'lipaidox_live_streaming.LiveStream',
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
