import uuid
from django.db import models
from .subscription import CreatorPlanSubscription
from ..constants import CreatorPlanTier, PlanPaymentStatus, PlanPaymentType
from lipaidox.creator_profile.models import CreatorProfile

class CreatorPlanPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name="plan_payments")
    plan_subscription = models.ForeignKey(CreatorPlanSubscription, on_delete=models.CASCADE, related_name="payments")
    plan_tier = models.CharField(max_length=20, choices=CreatorPlanTier.choices)

    # ── PAYMENT DETAILS ──
    payment_type = models.CharField(max_length=20, choices=PlanPaymentType.choices, default=PlanPaymentType.RENEWAL)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=20, choices=PlanPaymentStatus.choices, default=PlanPaymentStatus.PENDING)

    # ── PERIOD COVERED ──
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)

    # ── CREDIT TOP UP ──
    credits_purchased = models.IntegerField(null=True, blank=True)
    credits_duration_mins = models.IntegerField(null=True, blank=True)

    # ── GATEWAY ──
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    gateway_reference = models.CharField(max_length=255, null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)

    # ── FAILURE ──
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
        db_table = "creator_plan_payments"
        app_label = "lipaidox_creator_plans"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['attempted_at']),
        ]

    def __str__(self):
        return f"{self.payment_type} for {self.creator.display_name} - {self.amount_paid} {self.currency}"
