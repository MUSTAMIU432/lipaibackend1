import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class AudienceType(models.TextChoices):
    """Types of content audience"""
    GENERAL = 'general', 'General'
    ADULT = 'adult', 'Adult'
    TEEN = 'teen', 'Teen'
    MATURE = 'mature', 'Mature'
    FAMILY = 'family', 'Family'


class ContentScore(RecommendationTenantAwareModel):
    """
    Content Scores - Module 23
    Algorithmic scoring for content recommendations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='recommendation_scores'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='recommendation_content_scores'
    )

    # Score Components
    recency_score = models.DecimalField(max_digits=8, decimal_places=4, default=0.00)
    engagement_score = models.DecimalField(max_digits=8, decimal_places=4, default=0.00)
    purchase_score = models.DecimalField(max_digits=8, decimal_places=4, default=0.00)
    creator_tier_score = models.DecimalField(max_digits=8, decimal_places=4, default=0.00)
    velocity_score = models.DecimalField(max_digits=8, decimal_places=4, default=0.00)

    # Final Score
    total_score = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)

    # Raw Metrics Used
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)
    purchase_count = models.IntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)

    # Category Information
    primary_category = models.CharField(max_length=100, blank=True, null=True)
    audience_type = models.CharField(
        max_length=20,
        choices=AudienceType.choices,
        default=AudienceType.GENERAL
    )

    # Timestamps
    last_computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recommendation_content_scores'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['content'], name='idx_rec_content_scores_content'),
            models.Index(fields=['creator'], name='idx_rec_content_scores_creator'),
            models.Index(fields=['-total_score'], name='idx_content_scores_total_score'),
            models.Index(fields=['primary_category'], name='idx_content_scores_category'),
            models.Index(fields=['audience_type'], name='idx_content_scores_audience'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['content'],
                name='recommendation_content_scores_unique'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(recency_score__gte=0) &
                    models.Q(engagement_score__gte=0) &
                    models.Q(total_score__gte=0)
                ),
                name='scores_check'
            ),
        ]

    def __str__(self):
        return f"Content Score: {self.content.title} - {self.total_score:.2f}"

    def calculate_recency_score(self):
        """Calculate recency score based on content age"""
        from django.utils import timezone
        
        age_hours = (timezone.now() - self.content.created_at).total_seconds() / 3600
        
        # Exponential decay - newer content scores higher
        if age_hours <= 6:
            return 1.0
        elif age_hours <= 24:
            return 0.8
        elif age_hours <= 72:
            return 0.6
        elif age_hours <= 168:  # 7 days
            return 0.4
        else:
            return 0.2

    def calculate_engagement_score(self):
        """Calculate engagement score based on likes, comments, shares"""
        from lipaidox.content.models import ContentMedia
        
        media = self.content.media.all()
        if not media:
            return 0
        
        total_views = sum(m.view_count for m in media)
        total_likes = sum(m.like_count for m in media)
        total_comments = sum(m.comment_count for m in media)
        
        if total_views == 0:
            return 0
        
        # Engagement rate = (likes + comments + shares) / views
        engagement_rate = (total_likes + total_comments + self.share_count) / total_views
        
        # Normalize to 0-1 scale (5% engagement = 1.0 score)
        return min(engagement_rate / 0.05, 1.0)

    def calculate_purchase_score(self):
        """Calculate purchase score based on PPV purchases"""
        from lipaidox.ppv.models import PPVPurchase
        from lipaidox.content.models import ContentMedia
        
        media = self.content.media.all()
        if not media:
            return 0
        
        total_views = sum(m.view_count for m in media)
        if total_views == 0:
            return 0
        
        ppv_purchases = PPVPurchase.objects.filter(
            content=self.content,
            status='completed'
        ).count()
        
        purchase_rate = ppv_purchases / total_views
        
        # Normalize to 0-1 scale (2% purchase rate = 1.0 score)
        return min(purchase_rate / 0.02, 1.0)

    def calculate_creator_tier_score(self):
        """Calculate score based on creator tier and verification"""
        creator = self.creator
        
        # Base score from tier
        tier_scores = {
            'basic': 0.3,
            'premium': 0.6,
            'vip': 0.8,
            'enterprise': 1.0,
        }
        
        base_score = tier_scores.get(creator.tier.lower(), 0.3)
        
        # Bonus for verification
        if creator.is_verified:
            base_score += 0.2
        
        return min(base_score, 1.0)

    def calculate_velocity_score(self):
        """Calculate velocity score based on engagement growth rate"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get engagement from last 24 hours vs previous 24 hours
        now = timezone.now()
        recent_period = (now - timedelta(hours=24), now)
        previous_period = (now - timedelta(hours=48), now - timedelta(hours=24))
        
        def get_period_engagement(start, end):
            from lipaidox.recommendation.models import UserInteraction
            
            return UserInteraction.objects.filter(
                content=self.content,
                interacted_at__range=(start, end),
                interaction_type__in=['like', 'comment', 'share']
            ).count()
        
        recent_engagement = get_period_engagement(*recent_period)
        previous_engagement = get_period_engagement(*previous_period)
        
        if previous_engagement == 0:
            return recent_engagement > 0 and 0.5 or 0
        
        growth_rate = (recent_engagement - previous_engagement) / previous_engagement
        
        # Normalize to 0-1 scale (100% growth = 1.0 score)
        return min(max(growth_rate, 0), 1.0)

    def calculate_total_score(self):
        """Calculate overall content score with weighted components"""
        # Weight distribution
        weights = {
            'recency': 0.25,
            'engagement': 0.30,
            'purchase_rate': 0.20,
            'creator_tier': 0.15,
            'velocity': 0.10,
        }
        
        overall = (
            self.recency_score * weights['recency'] +
            self.engagement_score * weights['engagement'] +
            self.purchase_score * weights['purchase_rate'] +
            self.creator_tier_score * weights['creator_tier'] +
            self.velocity_score * weights['velocity']
        )
        
        self.total_score = min(overall, 1.0)
        self.save()
        
        return self.total_score

    def update_raw_metrics(self):
        """Update raw metrics from content and interactions"""
        from lipaidox.content.models import ContentMedia
        from lipaidox.recommendation.models import UserInteraction
        
        # Get media metrics
        media = self.content.media.all()
        self.view_count = sum(m.view_count for m in media)
        self.like_count = sum(m.like_count for m in media)
        self.comment_count = sum(m.comment_count for m in media)
        
        # Get interaction metrics
        interactions = UserInteraction.objects.filter(content=self.content)
        self.share_count = interactions.filter(interaction_type='share').count()
        self.purchase_count = interactions.filter(interaction_type='purchase').count()
        
        # Calculate engagement rate
        if self.view_count > 0:
            self.engagement_rate = (self.like_count + self.comment_count + self.share_count) / self.view_count
        else:
            self.engagement_rate = 0
        
        # Set category
        self.primary_category = self.content.category or 'general'
        
        self.save()

    @classmethod
    def calculate_all_scores(cls):
        """Calculate scores for all content"""
        from django.db import transaction
        
        contents = cls.objects.select_related('content', 'creator').all()
        
        for score_obj in contents:
            with transaction.atomic():
                score_obj.update_raw_metrics()
                score_obj.recency_score = score_obj.calculate_recency_score()
                score_obj.engagement_score = score_obj.calculate_engagement_score()
                score_obj.purchase_score = score_obj.calculate_purchase_score()
                score_obj.creator_tier_score = score_obj.calculate_creator_tier_score()
                score_obj.velocity_score = score_obj.calculate_velocity_score()
                score_obj.calculate_total_score()

    @classmethod
    def get_top_content(cls, limit=100, category=None, audience_type=None):
        """Get top scoring content"""
        queryset = cls.objects.select_related('content', 'creator')
        
        if category:
            queryset = queryset.filter(primary_category=category)
        if audience_type:
            queryset = queryset.filter(audience_type=audience_type)
        
        return queryset.order_by('-total_score')[:limit]

    @classmethod
    def get_content_by_score_range(cls, min_score=0.5, max_score=1.0, limit=50):
        """Get content within score range"""
        return cls.objects.filter(
            total_score__range=(min_score, max_score)
        ).select_related('content', 'creator').order_by('-total_score')[:limit]
