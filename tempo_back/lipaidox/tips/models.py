import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class TipStatus(models.TextChoices):
    """Status of tips"""
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class TipType(models.TextChoices):
    """Type of tip"""
    MONEY = 'money', 'Money'


class Tip(TenantAwareModel):
    """
    Money tips from fans to creators - Module 12
    Credit tips are handled by fan_credit_gifts_sent (Module 22)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # References
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='tips_sent'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='tips_received'
    )

    # Tip Type (only money tips here)
    tip_type = models.CharField(
        max_length=20,
        choices=TipType.choices,
        default=TipType.MONEY
    )

    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    message = models.TextField(blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)

    # Processing
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    status = models.CharField(
        max_length=20,
        choices=TipStatus.choices,
        default=TipStatus.PENDING
    )

    # Payment
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)

    # Related content (optional - can tip creator directly or via content)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tips'
    )
    live_stream_id = models.CharField(max_length=255, blank=True, null=True)

    # Refund
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)

    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tips'
        app_label = 'lipaidox_tips'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['fan'], name='idx_tips_fan'),
            models.Index(fields=['creator'], name='idx_tips_creator'),
            models.Index(fields=['content'], name='idx_tips_content'),
            models.Index(fields=['status'], name='idx_tips_status'),
            models.Index(fields=['sent_at'], name='idx_tips_sent'),
            models.Index(fields=['live_stream_id'], name='idx_tips_stream'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='tips_amount_check'),
            models.CheckConstraint(check=models.Q(platform_fee__gte=0), name='tips_platform_fee_check'),
            models.CheckConstraint(check=models.Q(net_amount__gte=0), name='tips_net_amount_check'),
            models.CheckConstraint(
                check=models.Q(net_amount=models.F('amount') - models.F('platform_fee')),
                name='tips_net_amount_calc'
            ),
        ]

    def __str__(self):
        return f"Tip: {self.fan.username} -> {self.creator.username} - {self.amount} {self.currency}"

    def calculate_fees(self):
        """Calculate platform fee and net amount for creator"""
        self.platform_fee = self.amount * (self.platform_fee_percent / 100)
        self.net_amount = self.amount - self.platform_fee

    def mark_completed(self):
        """Mark tip as completed and processed"""
        from django.utils import timezone
        self.status = TipStatus.COMPLETED
        self.processed_at = timezone.now()
        self.save()

    def process_refund(self, reason=None):
        """Process refund for tip"""
        from django.utils import timezone
        self.status = TipStatus.REFUNDED
        self.refunded_at = timezone.now()
        self.refund_reason = reason
        self.save()
