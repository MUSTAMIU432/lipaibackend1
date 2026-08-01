import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ContentScore(TenantAwareModel):
    """
    Content Scores - Module 23
    Algorithmic scoring for content recommendations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='scores'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='content_scores'
    )

    # Score Components
    recency_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    engagement_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    purchase_rate_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    creator_tier_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    velocity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    
    # Overall Score
    overall_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    score_rank = models.IntegerField(default=0)  # Global ranking
    
    # Trending Metrics
    trending_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    is_trending = models.BooleanField(default=False)
    trend_position = models.IntegerField(default=0)  # Position in trending list
    
    # Category Performance
    category_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    category_rank = models.IntegerField(default=0)
    
    # Quality Metrics
    quality_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    ai_authenticity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    
    # Timestamps
    last_calculated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'content_scores'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['content'], name='idx_content_scores_content'),
            models.Index(fields=['creator'], name='idx_content_scores_creator'),
            models.Index(fields=['-overall_score'], name='idx_content_scores_overall'),
            models.Index(fields=['-trending_score'], name='idx_content_scores_trending'),
            models.Index(fields=['is_trending'], name='idx_content_scores_is_trending'),
            models.Index(fields=['last_calculated_at'], name='idx_content_scores_calculated'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['content'],
                name='content_scores_unique'
            ),
            models.CheckConstraint(
                check=models.Q(overall_score__range=(0, 1)),
                name='overall_score_check'
            ),
            models.CheckConstraint(
                check=models.Q(trending_score__range=(0, 1)),
                name='trending_score_check'
            ),
        ]

    def __str__(self):
        return f"Content Score: {self.content.title} - {self.overall_score:.3f}"

    def calculate_recency_score(self):
        """Calculate recency score based on content age"""
        from django.utils import timezone
        import math
        
        age_hours = (timezone.now() - self.content.created_at).total_seconds() / 3600
        
        # Exponential decay - newer content scores higher
        # 0-6 hours: 1.0, 6-24 hours: 0.8, 24-72 hours: 0.6, 3-7 days: 0.4, 7+ days: 0.2
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
        
        # Engagement rate = (likes + comments) / views
        engagement_rate = (total_likes + total_comments) / total_views
        
        # Normalize to 0-1 scale (5% engagement = 1.0 score)
        return min(engagement_rate / 0.05, 1.0)

    def calculate_purchase_rate_score(self):
        """Calculate purchase rate score based on PPV purchases"""
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
        from lipaidox.content.models import ContentMedia
        
        # Get engagement from last 24 hours vs previous 24 hours
        now = timezone.now()
        recent_period = (now - timedelta(hours=24), now)
        previous_period = (now - timedelta(hours=48), now - timedelta(hours=24))
        
        def get_period_engagement(start, end):
            media = self.content.media.filter(
                created_at__range=(start, end)
            )
            return sum(m.like_count + m.comment_count for m in media)
        
        recent_engagement = get_period_engagement(*recent_period)
        previous_engagement = get_period_engagement(*previous_period)
        
        if previous_engagement == 0:
            return recent_engagement > 0 and 0.5 or 0
        
        growth_rate = (recent_engagement - previous_engagement) / previous_engagement
        
        # Normalize to 0-1 scale (100% growth = 1.0 score)
        return min(max(growth_rate, 0), 1.0)

    def calculate_overall_score(self):
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
            self.purchase_rate_score * weights['purchase_rate'] +
            self.creator_tier_score * weights['creator_tier'] +
            self.velocity_score * weights['velocity']
        )
        
        self.overall_score = min(overall, 1.0)
        self.save()
        
        return self.overall_score

    def update_trending_status(self, trending_threshold=0.7):
        """Update trending status based on score"""
        self.is_trending = self.overall_score >= trending_threshold
        self.save()

    @classmethod
    def calculate_all_scores(cls):
        """Calculate scores for all content"""
        from django.db import transaction
        
        contents = cls.objects.select_related('content', 'creator').all()
        
        for score_obj in contents:
            with transaction.atomic():
                score_obj.recency_score = score_obj.calculate_recency_score()
                score_obj.engagement_score = score_obj.calculate_engagement_score()
                score_obj.purchase_rate_score = score_obj.calculate_purchase_rate_score()
                score_obj.creator_tier_score = score_obj.calculate_creator_tier_score()
                score_obj.velocity_score = score_obj.calculate_velocity_score()
                score_obj.calculate_overall_score()
                score_obj.update_trending_status()

    @classmethod
    def get_trending_content(cls, limit=50):
        """Get trending content"""
        return cls.objects.filter(
            is_trending=True
        ).select_related('content', 'creator').order_by(
            '-trending_score', '-overall_score'
        )[:limit]

    @classmethod
    def get_top_content(cls, limit=100):
        """Get top scoring content"""
        return cls.objects.select_related('content', 'creator').order_by(
            '-overall_score'
        )[:limit]
