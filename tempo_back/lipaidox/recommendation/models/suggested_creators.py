import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class SuggestionReason(models.TextChoices):
    """Reasons for creator suggestions"""
    MATCHING_CATEGORY = 'matching_category', 'Matching Category'
    SIMILAR_TO_FOLLOWED = 'similar_to_followed', 'Similar to Followed'
    TRENDING_CREATOR = 'trending_creator', 'Trending Creator'
    NEW_VERIFIED_CREATOR = 'new_verified_creator', 'New Verified Creator'
    PLATFORM_FEATURED = 'platform_featured', 'Platform Featured'
    PURCHASED_CONTENT_BEFORE = 'purchased_content_before', 'Purchased Content Before'


class SuggestedCreator(RecommendationTenantAwareModel):
    """
    Suggested Creators - Module 23
    Creator recommendations for users to discover
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='recommendation_suggested_creators'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='recommendation_suggested_to_users'
    )
    suggestion_score = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
    rank_position = models.IntegerField()
    suggestion_reason = models.CharField(
        max_length=100,
        choices=SuggestionReason.choices
    )
    is_seen = models.BooleanField(default=False)
    is_followed = models.BooleanField(default=False)
    valid_until = models.DateTimeField()
    computed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recommendation_suggested_creators'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['user'], name='idx_rec_suggested_creators_usr'),
            models.Index(fields=['creator'], name='idx_rec_suggested_creators_cre'),
            models.Index(fields=['user', 'rank_position'], name='idx_rec_suggested_creators_rnk'),
            models.Index(fields=['valid_until'], name='idx_suggested_creators_valid'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'creator'],
                name='recommendation_suggested_creators_unique'
            ),
            models.CheckConstraint(
                check=models.Q(rank_position__gte=1),
                name='rank_check'
            ),
            models.CheckConstraint(
                check=models.Q(suggestion_score__gte=0),
                name='recommendation_suggestion_score_check'
            ),
        ]

    def __str__(self):
        return f"Suggested Creator: {self.user.username} -> {self.creator.user.username}"

    def mark_seen(self):
        """Mark suggestion as seen"""
        self.is_seen = True
        self.save()

    def mark_followed(self):
        """Mark suggestion as followed"""
        self.is_followed = True
        self.save()

    def is_valid(self):
        """Check if suggestion is still valid"""
        from django.utils import timezone
        return self.valid_until > timezone.now()

    @classmethod
    def get_user_suggestions(cls, user, limit=20, seen_only=False):
        """Get user's creator suggestions"""
        from django.utils import timezone
        
        queryset = cls.objects.filter(
            user=user,
            valid_until__gt=timezone.now()
        ).select_related('creator__user')
        
        if seen_only:
            queryset = queryset.filter(is_seen=True)
        else:
            queryset = queryset.filter(is_seen=False)
        
        return queryset.order_by('rank_position')[:limit]

    @classmethod
    def create_suggestion(cls, user, creator, score, reason, position=1, valid_days=7):
        """Create a creator suggestion"""
        from django.utils import timezone
        from datetime import timedelta
        
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            creator=creator,
            suggestion_score=score,
            suggestion_reason=reason,
            position=position,
            valid_until=timezone.now() + timedelta(days=valid_days)
        )

    @classmethod
    def generate_user_suggestions(cls, user, limit=20):
        """Generate creator suggestions for user"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.subscriptions.models import Subscription
        from lipaidox.recommendation.models import UserInteraction, TrendingContent
        
        # Clear existing suggestions
        cls.objects.filter(user=user).delete()
        
        # Get creators user already follows
        followed_creators = Subscription.objects.filter(
            user=user,
            is_active=True
        ).values_list('creator_id', flat=True)
        
        # Get potential creators to suggest
        from lipaidox.creator_profile.models import CreatorProfile
        
        potential_creators = CreatorProfile.objects.exclude(
            id__in=followed_creators
        ).exclude(
            user=user
        ).filter(
            user__is_active=True
        ).select_related('user').distinct()
        
        suggestions = []
        position = 1
        
        for creator in potential_creators:
            if position > limit:
                break
            
            # Calculate suggestion score
            score = cls._calculate_suggestion_score(user, creator, followed_creators)
            
            if score > 0.2:  # Minimum threshold
                reason = cls._determine_suggestion_reason(user, creator, followed_creators)
                
                suggestion = cls.create_suggestion(
                    user=user,
                    creator=creator,
                    score=score,
                    reason=reason,
                    position=position
                )
                
                suggestions.append(suggestion)
                position += 1
        
        return suggestions

    @classmethod
    def _calculate_suggestion_score(cls, user, creator, followed_creators):
        """Calculate suggestion score for user and creator"""
        from lipaidox.recommendation.models import UserInteraction, TrendingContent
        
        score = 0.0
        
        # Category match score
        user_categories = cls._get_user_preferred_categories(user)
        creator_categories = cls._get_creator_categories(creator)
        
        if user_categories and creator_categories:
            category_overlap = set(user_categories) & set(creator_categories)
            if category_overlap:
                score += len(category_overlap) / len(creator_categories) * 0.4
        
        # Similarity to followed creators
        similarity_score = cls._calculate_creator_similarity(user, creator, followed_creators)
        score += similarity_score * 0.3
        
        # Trending bonus
        if TrendingContent.objects.filter(creator=creator).exists():
            score += 0.2
        
        # Verification bonus
        if creator.is_verified:
            score += 0.1
        
        return min(score, 1.0)

    @classmethod
    def _determine_suggestion_reason(cls, user, creator, followed_creators):
        """Determine the reason for suggestion"""
        from lipaidox.recommendation.models import TrendingContent
        
        user_categories = cls._get_user_preferred_categories(user)
        creator_categories = cls._get_creator_categories(creator)
        
        if user_categories and creator_categories:
            category_overlap = set(user_categories) & set(creator_categories)
            if category_overlap:
                return SuggestionReason.MATCHING_CATEGORY
        
        if TrendingContent.objects.filter(creator=creator).exists():
            return SuggestionReason.TRENDING_CREATOR
        
        if creator.is_verified:
            return SuggestionReason.NEW_VERIFIED_CREATOR
        
        similarity_score = cls._calculate_creator_similarity(user, creator, followed_creators)
        if similarity_score > 0.5:
            return SuggestionReason.SIMILAR_TO_FOLLOWED
        
        return SuggestionReason.PLATFORM_FEATURED

    @classmethod
    def _calculate_creator_similarity(cls, user, creator, followed_creators):
        """Calculate similarity between creator and user's followed creators"""
        if not followed_creators:
            return 0
        
        from lipaidox.creator_profile.models import CreatorProfile
        
        # Get followed creators
        followed = CreatorProfile.objects.filter(id__in=followed_creators)
        
        if not followed.exists():
            return 0
        
        # Calculate average similarity
        similarities = []
        
        for followed_creator in followed:
            # Compare categories
            creator_cats = set(cls._get_creator_categories(creator))
            followed_cats = set(cls._get_creator_categories(followed_creator))
            
            if creator_cats and followed_cats:
                overlap = creator_cats & followed_cats
                similarity = len(overlap) / len(creator_cats | followed_cats)
                similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0

    @classmethod
    def _get_user_preferred_categories(cls, user):
        """Get user's preferred categories based on interaction history"""
        from lipaidox.recommendation.models import UserInteraction
        
        interactions = UserInteraction.objects.filter(
            user=user,
            content__isnull=False
        ).values('content__category').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        return [interaction['content__category'] for interaction in interactions if interaction['content__category']]

    @classmethod
    def _get_creator_categories(cls, creator):
        """Get creator's content categories"""
        from lipaidox.content.models import Content
        
        return Content.objects.filter(
            creator=creator
        ).values_list('category', flat=True).distinct()

    @classmethod
    def get_suggestion_analytics(cls, user, days=7):
        """Get suggestion performance analytics for user"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        suggestions = cls.objects.filter(
            user=user,
            created_at__gte=cutoff_date
        )
        
        total = suggestions.count()
        seen = suggestions.filter(is_seen=True).count()
        followed = suggestions.filter(is_followed=True).count()
        
        return {
            'total_suggestions': total,
            'seen_count': seen,
            'seen_rate': (seen / total * 100) if total > 0 else 0,
            'followed_count': followed,
            'follow_rate': (followed / seen * 100) if seen > 0 else 0,
        }

    @classmethod
    def cleanup_expired_suggestions(cls):
        """Remove expired suggestions"""
        from django.utils import timezone
        
        return cls.objects.filter(
            valid_until__lte=timezone.now()
        ).delete()[0]
