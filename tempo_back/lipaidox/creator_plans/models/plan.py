import uuid
import strawberry
from django.db import models
from multitenant.models import TenantAwareModel
from ..constants import CreatorPlanTier

class CreatorPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tier = models.CharField(max_length=20, choices=CreatorPlanTier.choices, unique=True)
    name = models.CharField(max_length=100)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(null=True, blank=True)

    # ── FEATURE FLAGS ──
    can_monetize = models.BooleanField(default=False)
    can_live_stream = models.BooleanField(default=False)
    can_sell_ppv = models.BooleanField(default=False)
    can_receive_tips = models.BooleanField(default=False)
    can_sell_subscriptions = models.BooleanField(default=False)
    can_sell_custom_content = models.BooleanField(default=False)

    # ── LIVE CREDITS ──
    monthly_free_credits = models.IntegerField(default=0)
    unlimited_live_sessions = models.IntegerField(default=0)
    credit_top_up_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    credit_top_up_duration_mins = models.IntegerField(null=True, blank=True)

    # ── LIMITS ──
    max_content_uploads_per_month = models.IntegerField(null=True, blank=True)
    max_file_size_mb = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "creator_plans"
        app_label = "lipaidox_creator_plans"
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name} tier"
