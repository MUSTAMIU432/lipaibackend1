import uuid
from django.db import models
from django.conf import settings
from .subscription import Subscription
from lipaidox.creator_profile.models import CreatorProfile

class SubscriptionPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'

class SubscriptionPaymentType(models.TextChoices):
    INITIAL = 'initial', 'Initial'
    RENEWAL = 'renewal', 'Renewal'
    RETRY = 'retry', 'Retry'
    MANUAL = 'manual', 'Manual'

class SubscriptionPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    fan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE)

    # ── PAYMENT DETAILS ──
    payment_type = models.CharField(
        max_length=20, 
        choices=SubscriptionPaymentType.choices, 
        default=SubscriptionPaymentType.RENEWAL
    )
    payment_number = models.IntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(
        max_length=20, 
        choices=SubscriptionPaymentStatus.choices, 
        default=SubscriptionPaymentStatus.PENDING
    )

    # ── BILLING PERIOD THIS PAYMENT COVERS ──
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    # ── PAYMENT METHOD ──
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    gateway_reference = models.CharField(max_length=255, null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)

    # ── FAILURE HANDLING ──
    failure_reason = models.TextField(null=True, blank=True)
    retry_attempt = models.IntegerField(default=0)

    # ── REFUND ──
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # ── TIMESTAMPS ──
    attempted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_payments"
        app_label = "lipaidox_subscriptions"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['attempted_at']),
        ]

    def save(self, *args, **kwargs):
        # Auto-calculate net_amount if not set
        if self.net_amount is None and self.amount_paid is not None:
            self.net_amount = self.amount_paid - self.platform_fee
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment #{self.payment_number} for {self.subscription.id} ({self.status})"
