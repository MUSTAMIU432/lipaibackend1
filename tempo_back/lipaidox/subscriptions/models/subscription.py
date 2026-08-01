import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from django.conf import settings
from lipaidox.creator_profile.models import CreatorProfile

class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'
    PAST_DUE = 'past_due', 'Past Due'
    PAUSED = 'paused', 'Paused'
    PENDING = 'pending', 'Pending'

class SubscriptionBillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    ANNUAL = 'annual', 'Annual'

class Subscription(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name="subscribers")

    # ── PRICING ──
    price_at_signup = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    billing_cycle = models.CharField(
        max_length=20, 
        choices=SubscriptionBillingCycle.choices, 
        default=SubscriptionBillingCycle.MONTHLY
    )
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)

    # ── STATUS ──
    status = models.CharField(
        max_length=20, 
        choices=SubscriptionStatus.choices, 
        default=SubscriptionStatus.PENDING
    )

    # ── BILLING PERIOD ──
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    # ── TRIAL ──
    is_trial = models.BooleanField(default=False)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # ── CANCELLATION ──
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=True)

    # ── RETRY TRACKING ──
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    max_retries = models.IntegerField(default=3)

    # ── PAYMENT METHOD ──
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    # ── TIMESTAMPS ──
    started_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        app_label = "lipaidox_subscriptions"
        unique_together = (('fan', 'creator'),)
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['next_billing_date']),
            models.Index(fields=['current_period_end']),
        ]

    def __str__(self):
        return f"{self.fan.username} -> {self.creator.display_name} ({self.status})"
