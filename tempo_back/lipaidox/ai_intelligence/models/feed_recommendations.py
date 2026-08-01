import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class FeedRecommendation(TenantAwareModel):
    """
    Feed Recommendations - Module 23
    Personalized content recommendations for users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='feed_recommendations'
    )
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='feed_recommendations'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='user_recommendations'
    )

    # Recommendation Scores
    relevance_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    interest_match_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    social_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    diversity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    freshness_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    
    # Overall Recommendation Score
    recommendation_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    feed_position = models.IntegerField(default=0)  # Position in user's feed
    
    # Recommendation Context
    recommendation_reason = models.TextField(blank=True, null=True)
    weight_factors = models.JSONField(default=dict, blank=True)  # Store individual factor weights
    
    # User Interaction Tracking
    shown_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    liked_at = models.DateTimeField(null=True, blank=True)
    shared_at = models.DateTimeField(null=True, blank=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    
    # Feedback
    user_feedback = models.IntegerField(default=0)  # -1 (dislike) to 1 (like)
    engagement_time_seconds = models.IntegerField(default=0)
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'feed_recommendations'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['user'], name='idx_feed_recommendations_user'),
            models.Index(fields=['content'], name='idx_feed_rec_content'),
            models.Index(fields=['-recommendation_score'], name='idx_feed_rec_score'),
            models.Index(fields=['feed_position'], name='idx_feed_rec_position'),
            models.Index(fields=['generated_at'], name='idx_feed_rec_generated'),
            models.Index(fields=['expires_at'], name='idx_feed_rec_expires'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content'],
                name='feed_recommendations_unique'
            ),
            models.CheckConstraint(
                check=models.Q(recommendation_score__range=(0, 1)),
                name='recommendation_score_check'
            ),
            models.CheckConstraint(
                check=models.Q(user_feedback__range=(-1, 1)),
                name='user_feedback_check'
            ),
        ]

    def __str__(self):
        return f"Feed Recommendation: {self.user.username} -> {self.content.title}"

    def calculate_interest_match_score(self):
        """Calculate interest match based on user's category preferences"""
        from lipaidox.content.models import Content
        
        # Get user's interaction history by category
        user_categories = Content.objects.filter(
            # This would need to be implemented based on user's viewing history
            # For now, use creator's category as proxy
            creator__user__subscriptions__user=self.user,
            creator__user__subscriptions__is_active=True
        ).values_list('category', flat=True).distinct()
        
        if self.content.category in user_categories:
            return 0.8  # High match for subscribed categories
        elif self.content.category in ['general', 'trending']:
            return 0.5  # Medium match for general content
        else:
            return 0.2  # Low match for new categories

    def calculate_social_score(self):
        """Calculate social score based on user's social connections"""
        from lipaidox.subscriptions.models import Subscription
        
        # Check if user follows creator
        is_subscribed = Subscription.objects.filter(
            user=self.user,
            creator=self.creator,
            is_active=True
        ).exists()
        
        if is_subscribed:
            return 1.0  # Highest score for subscribed creators
        elif self.creator.followers.filter(id=self.user.id).exists():
            return 0.7  # High score for followed creators
        else:
            return 0.3  # Base score for discovery

    def calculate_diversity_score(self):
        """Calculate diversity score to ensure feed variety"""
        from lipaidox.content.models import Content
        
        # Check user's recent recommendations
        recent_categories = FeedRecommendation.objects.filter(
            user=self.user,
            generated_at__gte=timezone.now() - timedelta(days=1)
        ).values_list('content__category', flat=True)
        
        # Boost score if this adds variety
        if self.content.category not in recent_categories:
            return 0.8  # High diversity value
        else:
            return 0.4  # Lower if similar to recent content

    def calculate_freshness_score(self):
        """Calculate freshness score based on content age"""
        from django.utils import timezone
        import math
        
        age_hours = (timezone.now() - self.content.created_at).total_seconds() / 3600
        
        # Similar to recency score but for recommendations
        if age_hours <= 2:
            return 1.0
        elif age_hours <= 6:
            return 0.8
        elif age_hours <= 24:
            return 0.6
        elif age_hours <= 72:
            return 0.4
        else:
            return 0.2

    def calculate_recommendation_score(self):
        """Calculate overall recommendation score"""
        # Dynamic weights based on user behavior
        weights = {
            'interest_match': 0.30,
            'social': 0.35,
            'diversity': 0.15,
            'freshness': 0.20,
        }
        
        # Adjust weights based on user's engagement patterns
        if self.user_feedback > 0:
            weights['social'] += 0.1  # Boost social if user likes social content
            weights['interest_match'] -= 0.1
        
        overall = (
            self.interest_match_score * weights['interest_match'] +
            self.social_score * weights['social'] +
            self.diversity_score * weights['diversity'] +
            self.freshness_score * weights['freshness']
        )
        
        self.recommendation_score = min(overall, 1.0)
        self.weight_factors = weights
        self.save()
        
        return self.recommendation_score

    def record_interaction(self, interaction_type):
        """Record user interaction with recommended content"""
        from django.utils import timezone
        
        now = timezone.now()
        
        if interaction_type == 'shown':
            self.shown_at = now
        elif interaction_type == 'viewed':
            self.viewed_at = now
        elif interaction_type == 'liked':
            self.liked_at = now
            self.user_feedback = 1
        elif interaction_type == 'shared':
            self.shared_at = now
            self.user_feedback = 1
        elif interaction_type == 'purchased':
            self.purchased_at = now
            self.user_feedback = 1
        elif interaction_type == 'skipped':
            self.skipped_at = now
            self.user_feedback = -0.5
        
        self.save()

    def update_engagement_time(self, seconds):
        """Update engagement time"""
        self.engagement_time_seconds += seconds
        self.save()

    def is_expired(self):
        """Check if recommendation has expired"""
        from django.utils import timezone
        return self.expires_at and self.expires_at <= timezone.now()

    @classmethod
    def generate_user_feed(cls, user, limit=50):
        """Generate personalized feed for user"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get user's subscriptions and interests
        from lipaidox.subscriptions.models import Subscription
        from lipaidox.content.models import Content
        
        subscribed_creators = Subscription.objects.filter(
            user=user,
            is_active=True
        ).values_list('creator_id', flat=True)
        
        # Get content from subscribed creators + high-scoring content
        content_queryset = Content.objects.filter(
            models.Q(creator_id__in=subscribed_creators) |
            models.Q(scores__overall_score__gte=0.7)
        ).select_related('creator', 'scores').distinct()
        
        recommendations = []
        
        for content in content_queryset:
            # Check if recommendation already exists
            existing = cls.objects.filter(user=user, content=content).first()
            if existing and not existing.is_expired():
                recommendations.append(existing)
                continue
            
            # Create new recommendation
            rec = cls.objects.create(
                user=user,
                content=content,
                creator=content.creator,
                tenant=user.tenant,
                expires_at=timezone.now() + timedelta(hours=24)
            )
            
            # Calculate scores
            rec.interest_match_score = rec.calculate_interest_match_score()
            rec.social_score = rec.calculate_social_score()
            rec.diversity_score = rec.calculate_diversity_score()
            rec.freshness_score = rec.calculate_freshness_score()
            rec.calculate_recommendation_score()
            
            recommendations.append(rec)
        
        # Sort by recommendation score and limit
        recommendations.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        # Update feed positions
        for i, rec in enumerate(recommendations[:limit]):
            rec.feed_position = i + 1
            rec.save()
        
        return recommendations[:limit]

    @classmethod
    def get_user_feed(cls, user, limit=50):
        """Get existing user feed or generate new one"""
        from django.utils import timezone
        
        # Check for existing fresh recommendations
        existing_feed = cls.objects.filter(
            user=user,
            expires_at__gt=timezone.now()
        ).select_related('content', 'creator').order_by(
            '-recommendation_score'
        )[:limit]
        
        if len(existing_feed) >= limit // 2:
            return existing_feed
        
        # Generate new recommendations
        return cls.generate_user_feed(user, limit)
