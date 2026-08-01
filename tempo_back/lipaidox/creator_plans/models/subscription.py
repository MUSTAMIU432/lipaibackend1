import uuid
from django.db import models
from django.conf import settings
from ..constants import CreatorPlanTier, CreatorPlanStatus
from lipaidox.creator_profile.models import CreatorProfile

class CreatorPlanSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField(CreatorProfile, on_delete=models.CASCADE, related_name="plan_subscription")
    plan_tier = models.CharField(max_length=20, choices=CreatorPlanTier.choices, default=CreatorPlanTier.FREE)

    # ── PRICING ──
    price_at_signup = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='USD')

    # ── STATUS ──
    status = models.CharField(max_length=20, choices=CreatorPlanStatus.choices, default=CreatorPlanStatus.ACTIVE)

    # ── BILLING PERIOD ──
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)

    # ── CANCELLATION ──
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=True)
    downgrade_to_tier = models.CharField(max_length=20, choices=CreatorPlanTier.choices, null=True, blank=True)

    # ── LIVE CREDITS ──
    available_credits = models.IntegerField(default=0)
    credits_reset_at = models.DateTimeField(null=True, blank=True)

    # ── PAYMENT METHOD ──
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    # ── RETRY TRACKING ──
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    max_retries = models.IntegerField(default=3)

    # ── TIMESTAMPS ──
    started_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "creator_plan_subscriptions"
        app_label = "lipaidox_creator_plans"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['next_billing_date']),
        ]

    def __str__(self):
        return f"{self.creator.display_name} -> {self.plan_tier} ({self.status})"
