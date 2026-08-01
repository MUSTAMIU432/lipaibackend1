import uuid
from django.db import models
from lipaidox.creator_profile.models import CreatorProfile

class CreatorLiveCreditUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name="credit_usage")
    live_stream_id = models.UUIDField(null=True, blank=True) # Reference to live stream module later
    credits_used = models.IntegerField(default=1)
    duration_mins = models.IntegerField(default=15)
    is_free_credit = models.BooleanField(default=False)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "creator_live_credit_usage"
        app_label = "lipaidox_creator_plans"
        indexes = [
            models.Index(fields=['used_at']),
        ]

    def __str__(self):
        return f"{self.creator.display_name}: {self.credits_used} credits at {self.used_at}"

class CreatorPurchasedCredits(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name="purchased_credits")
    credits_purchased = models.IntegerField()
    credits_remaining = models.IntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment = models.ForeignKey(
        'lipaidox_creator_plans.CreatorPlanPayment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "creator_purchased_credits"
        app_label = "lipaidox_creator_plans"

    def __str__(self):
        return f"{self.creator.display_name}: {self.credits_remaining}/{self.credits_purchased} credits"
