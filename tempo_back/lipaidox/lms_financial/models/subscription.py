import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .plan import LmsPlan

class SubscriptionStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'
    TRIALING = 'trialing', 'Trialing'

class LmsSubscription(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="lms_subscriptions")
    plan = models.ForeignKey(LmsPlan, on_delete=models.PROTECT, related_name="subscriptions")
    
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Integration Fields
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_subscriptions"
        app_label = "lms_financial"

    def __str__(self):
        return f"{self.student.user.username} - {self.plan.name} ({self.status})"
