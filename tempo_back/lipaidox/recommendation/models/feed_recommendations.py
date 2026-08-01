import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class RecommendationReason(models.TextChoices):
    """Reasons for content recommendations"""
    FOLLOWED_CREATOR = 'followed_creator', 'Followed Creator'
    SUBSCRIBED_CREATOR = 'subscribed_creator', 'Subscribed Creator'
    MATCHING_CATEGORY = 'matching_category', 'Matching Category'
    TRENDING = 'trending', 'Trending'
    SIMILAR_CONTENT = 'similar_content', 'Similar Content'
    NEW_CREATOR_DISCOVERY = 'new_creator_discovery', 'New Creator Discovery'
    PURCHASED_BEFORE = 'purchased_before', 'Purchased Before'
    PLATFORM_FEATURED = 'platform_featured', 'Platform Featured'


class FeedRecommendation(RecommendationTenantAwareModel):
    """
    Feed Recommendations - Module 23
    Personalized content recommendations for users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='recommendation_feed_recommendations'
    )
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='recommendation_user_feed_recommendations'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='recommendation_user_feed_recommendations'
    )

    # Recommendation Detail
    recommendation_score = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
    recommendation_reason = models.CharField(
        max_length=100,
        choices=RecommendationReason.choices
    )
    position = models.IntegerField()
    is_seen = models.BooleanField(default=False)
    is_interacted = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)
    
    # Ad Engine specific
    is_ad = models.BooleanField(default=False)
    ad_campaign = models.ForeignKey(
        'lipaidox_recommendation.PromotedContent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feed_impressions'
    )

    # Validity
    valid_until = models.DateTimeField()

    # Timestamps
    computed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recommendation_feed_recommendations'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['user'], name='idx_feed_recs_user'),
            models.Index(fields=['content'], name='idx_feed_recs_content'),
            models.Index(fields=['-recommendation_score'], name='idx_feed_recs_score'),
            models.Index(fields=['user', 'position'], name='idx_feed_recs_position'),
            models.Index(fields=['valid_until'], name='idx_feed_recs_valid_until'),
            models.Index(fields=['is_seen'], name='idx_feed_recs_is_seen'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content'],
                name='recommendation_feed_recommendations_unique'
            ),
            models.CheckConstraint(
                check=models.Q(position__gte=1),
                name='position_check'
            ),
            models.CheckConstraint(
                check=models.Q(recommendation_score__gte=0),
                name='recommendation_feed_score_check'
            ),
        ]

    def __str__(self):
        return f"Feed Rec: {self.user.username} -> {self.content.title} (Pos: {self.position})"

    def mark_seen(self):
        """Mark recommendation as seen"""
        from django.utils import timezone
        self.is_seen = True
        self.seen_at = timezone.now()
        self.save()

    def mark_interacted(self):
        """Mark recommendation as interacted"""
        self.is_interacted = True
        self.save()

    def is_valid(self):
        """Check if recommendation is still valid"""
        from django.utils import timezone
        return self.valid_until > timezone.now()

    @classmethod
    def get_user_feed(cls, user, limit=50, seen_only=False):
        """Get user's feed recommendations and inject Ads"""
        from django.utils import timezone
        from .promoted_content import PromotedContent, AdStatus
        
        queryset = cls.objects.filter(
            user=user,
            valid_until__gt=timezone.now()
        ).select_related('content', 'creator')
        
        if seen_only:
            queryset = queryset.filter(is_seen=True)
        else:
            queryset = queryset.filter(is_seen=False)
        
        feed = list(queryset.order_by('position')[:limit])
        
        # Determine if user is premium
        is_premium = False
        if hasattr(user, 'profile') and user.profile.plan_tier != 'free':
            is_premium = True
            
        # Also check general subscriptions if 'premium' refers to subscribing to platform, etc.
        # But 'plan_tier' is the standard way a creator is 'Premium'.
            
        if not is_premium and feed:
            # Fetch random active ads
            active_ads = list(PromotedContent.objects.filter(
                status=AdStatus.ACTIVE,
                start_date__lte=timezone.now(),
                end_date__gt=timezone.now()
            ).exclude(spent__gte=models.F('budget')).order_by('?')[:max(1, limit // 5)])
            
            if active_ads:
                ad_idx = 0
                # Inject 1 ad every 5 organic posts
                for i in range(4, len(feed) + len(active_ads), 5):
                    if ad_idx < len(active_ads) and i < len(feed):
                        ad = active_ads[ad_idx]
                        # Create an ad placeholder recommendation
                        ad_rec = cls(
                            user=user,
                            content=ad.content,
                            creator=ad.creator,
                            is_ad=True,
                            ad_campaign=ad,
                            position=i,
                            recommendation_score=1.0,  # Ads have high artificial relevance
                        )
                        feed.insert(i, ad_rec)
                        
                        # Increment ad metrics (simplified)
                        ad.impressions += 1
                        ad.save(update_fields=['impressions'])
                        ad_idx += 1
                        
        return feed

    @classmethod
    def create_recommendation(cls, user, content, score, reason, position=1, valid_hours=24):
        """Create a feed recommendation"""
        from django.utils import timezone
        from datetime import timedelta
        
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            content=content,
            creator=content.creator,
            recommendation_score=score,
            recommendation_reason=reason,
            position=position,
            valid_until=timezone.now() + timedelta(hours=valid_hours)
        )

    @classmethod
    def generate_user_feed(cls, user, limit=50):
        """Generate personalized feed for user"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.recommendation.models import ContentScore, UserInteraction
        from lipaidox.subscriptions.models import Subscription
        
        # Clear existing recommendations
        cls.objects.filter(user=user).delete()
        
        # Get user's subscriptions and interests
        subscribed_creators = Subscription.objects.filter(
            user=user,
            is_active=True
        ).values_list('creator_id', flat=True)
        
        # Get content scores
        content_scores = ContentScore.objects.select_related('content', 'creator').all()
        
        recommendations = []
        position = 1
        
        for score in content_scores:
            if position > limit:
                break
            
            # Calculate recommendation score based on user preferences
            rec_score = cls._calculate_recommendation_score(
                user, score.content, score, subscribed_creators
            )
            
            if rec_score > 0.3:  # Minimum threshold
                reason = cls._determine_recommendation_reason(
                    user, score.content, subscribed_creators
                )
                
                rec = cls.create_recommendation(
                    user=user,
                    content=score.content,
                    score=rec_score,
                    reason=reason,
                    position=position
                )
                
                recommendations.append(rec)
                position += 1
        
        return recommendations

    @classmethod
    def _calculate_recommendation_score(cls, user, content, content_score, subscribed_creators):
        """Calculate recommendation score for user and content"""
        score = content_score.total_score
        
        # Boost for subscribed creators
        if content.creator_id in subscribed_creators:
            score *= 1.5
        
        # Boost for followed creators
        if content.creator.followers.filter(id=user.id).exists():
            score *= 1.3
        
        # Boost for matching categories
        user_categories = cls._get_user_preferred_categories(user)
        if content.category in user_categories:
            score *= 1.2
        
        # Boost for trending content
        if content_score.total_score > 0.8:
            score *= 1.1
        
        return min(score, 1.0)

    @classmethod
    def _determine_recommendation_reason(cls, user, content, subscribed_creators):
        """Determine the reason for recommendation"""
        if content.creator_id in subscribed_creators:
            return RecommendationReason.SUBSCRIBED_CREATOR
        elif content.creator.followers.filter(id=user.id).exists():
            return RecommendationReason.FOLLOWED_CREATOR
        elif content.category in cls._get_user_preferred_categories(user):
            return RecommendationReason.MATCHING_CATEGORY
        elif content.total_score > 0.8:
            return RecommendationReason.TRENDING
        else:
            return RecommendationReason.NEW_CREATOR_DISCOVERY

    @classmethod
    def _get_user_preferred_categories(cls, user):
        """Get user's preferred categories based on interaction history"""
        from lipaidox.recommendation.models import UserInteraction
        
        # Get categories from user's interactions
        interactions = UserInteraction.objects.filter(
            user=user,
            content__isnull=False
        ).values('content__category').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        return [interaction['content__category'] for interaction in interactions]

    @classmethod
    def get_feed_analytics(cls, user, days=7):
        """Get feed performance analytics for user"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        recommendations = cls.objects.filter(
            user=user,
            created_at__gte=cutoff_date
        )
        
        total = recommendations.count()
        seen = recommendations.filter(is_seen=True).count()
        interacted = recommendations.filter(is_interacted=True).count()
        
        return {
            'total_recommendations': total,
            'seen_count': seen,
            'seen_rate': (seen / total * 100) if total > 0 else 0,
            'interacted_count': interacted,
            'interaction_rate': (interacted / seen * 100) if seen > 0 else 0,
        }
