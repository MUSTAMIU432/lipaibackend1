import uuid
from django.db import models
from django.utils import timezone
from .base import RecommendationTenantAwareModel

class AdStatus(models.TextChoices):
    PENDING = 'pending', 'Pending Approval'
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    COMPLETED = 'completed', 'Completed'
    REJECTED = 'rejected', 'Rejected'

class PromotedContent(RecommendationTenantAwareModel):
    """
    Ads Engine - Allow creators to pay to promote their content.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='promotions'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='promoted_campaigns'
    )
    
    # Financials
    budget = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total budget paid")
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Targeting
    target_category = models.CharField(max_length=50, blank=True, null=True)
    
    # Performance
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=AdStatus.choices, default=AdStatus.PENDING)
    
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recommendation_promoted_content'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        return f"Promo for {self.content.title} by {self.creator.username}"

    def is_active(self):
        return self.status == AdStatus.ACTIVE and self.start_date <= timezone.now() < self.end_date and self.spent < self.budget
