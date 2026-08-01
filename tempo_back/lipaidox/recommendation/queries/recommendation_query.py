import strawberry
from typing import Optional, List
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta, date

from ..models import (
    UserInteraction, InteractionType,
    ContentScore, AudienceType,
    FeedRecommendation, RecommendationReason,
    TrendingContent,
    SuggestedCreator, SuggestionReason,
    UserInterestProfile
)

from ..schema.recommendation_schema import (
    # Types
    UserInteractionType, ContentScoreType, RecommendationFeedType,
    TrendingContentType, RecommendationCreatorType, UserInterestProfileType,
    
    # Input Types
    RecordInteractionInput, RecommendationFilterInput, TrendingFilterInput,
    SuggestionFilterInput,
    
    # Analytics Types
    FeedAnalytics, SuggestionAnalytics, CategoryWeight, ProfileSummary,
    InteractionTypeStats, PlatformInteractionStats, FeedRecommendationPerformance,
    CreatorSuggestionPerformance, RecommendationPerformance
)

from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_admin(user):
    """Check if user is admin"""
    if user.role not in [UserRoles.ADMIN, 'superadmin']:
        raise Exception("Admin access required")
    return True


@strawberry.type
class RecommendationQuery:
    # User Interaction Queries
    @strawberry.field
    def my_interactions(
        self,
        info: strawberry.types.Info,
        interactionType: Optional[str] = None,
        days: int = 30,
        limit: int = 100
    ) -> List[UserInteractionType]:
        """Get current user's interactions"""
        user = require_auth(info)
        
        queryset = UserInteraction.get_user_interactions(
            user=user,
            interaction_type=interactionType,
            days=days
        ).select_related('content', 'creator').order_by('-interacted_at')[:limit]
        
        return [UserInteractionType.from_model(item) for item in queryset]

    @strawberry.field
    def content_interactions(
        self,
        info: strawberry.types.Info,
        contentId: strawberry.ID,
        interactionType: Optional[str] = None,
        days: int = 30
    ) -> List[UserInteractionType]:
        """Get interactions for specific content"""
        user = require_auth(info)
        
        queryset = UserInteraction.get_content_interactions(
            content_id=contentId,
            interaction_type=interactionType,
            days=days
        ).select_related('user').order_by('-interacted_at')
        
        return [UserInteractionType.from_model(item) for item in queryset]

    # Content Score Queries
    @strawberry.field
    def content_scores(
        self,
        info: strawberry.types.Info,
        contentId: Optional[strawberry.ID] = None,
        creatorId: Optional[strawberry.ID] = None,
        filter: Optional[RecommendationFilterInput] = None,
        limit: int = 50
    ) -> List[ContentScoreType]:
        """Get content scores"""
        user = require_auth(info)
        
        queryset = ContentScore.objects.filter(tenant=user.tenant)
        
        if contentId:
            queryset = queryset.filter(content_id=contentId)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)
        
        if filter:
            if filter.category:
                queryset = queryset.filter(primary_category=filter.category)
            if filter.audienceType:
                queryset = queryset.filter(audience_type=filter.audienceType)
            if filter.minScore:
                queryset = queryset.filter(total_score__gte=filter.minScore)
            if filter.maxScore:
                queryset = queryset.filter(total_score__lte=filter.maxScore)
        
        scores = queryset.select_related('content', 'creator').order_by('-total_score')[:limit]
        
        return [ContentScoreType.from_model(score) for score in scores]

    @strawberry.field
    def top_content(
        self,
        info: strawberry.types.Info,
        category: Optional[str] = None,
        audienceType: Optional[str] = None,
        limit: int = 100
    ) -> List[ContentScoreType]:
        """Get top scoring content"""
        user = require_auth(info)
        
        top_content = ContentScore.get_top_content(
            limit=limit,
            category=category,
            audience_type=audienceType
        )
        
        return [ContentScoreType.from_model(score) for score in top_content]

    # Feed Recommendation Queries
    @strawberry.field
    def my_feed(
        self,
        info: strawberry.types.Info,
        limit: int = 50,
        filter: Optional[RecommendationFilterInput] = None
    ) -> List[RecommendationFeedType]:
        """Get personalized feed for current user"""
        user = require_auth(info)
        
        queryset = FeedRecommendation.get_user_feed(user, limit=limit)
        
        if filter:
            if filter.seenOnly is not None:
                queryset = queryset.filter(is_seen=filter.seenOnly)
        
        return [RecommendationFeedType.from_model(rec) for rec in queryset]

    @strawberry.field
    def feed_analytics(
        self,
        info: strawberry.types.Info,
        days: int = 7
    ) -> FeedAnalytics:
        """Get feed performance analytics"""
        user = require_auth(info)
        
        analytics = FeedRecommendation.get_feed_analytics(user, days=days)
        
        return FeedAnalytics(
            totalRecommendations=analytics['total_recommendations'],
            seenCount=analytics['seen_count'],
            seenRate=analytics['seen_rate'],
            interactedCount=analytics['interacted_count'],
            interactionRate=analytics['interaction_rate']
        )

    # Trending Content Queries
    @strawberry.field
    def trending_content(
        self,
        info: strawberry.types.Info,
        filter: Optional[TrendingFilterInput] = None,
        limit: int = 50
    ) -> List[TrendingContentType]:
        """Get trending content"""
        user = require_auth(info)
        
        window_hours = filter.trendWindowHours if filter else 24
        
        trending = TrendingContent.get_trending_content(
            category=filter.category if filter else None,
            audience_type=filter.audienceType if filter else None,
            window_hours=window_hours,
            limit=limit
        )
        
        return [TrendingContentType.from_model(item) for item in trending]

    @strawberry.field
    def trending_categories(
        self,
        info: strawberry.types.Info,
        limit: int = 10
    ) -> List[str]:
        """Get trending categories"""
        user = require_auth(info)
        
        trending_cats = TrendingContent.get_trending_categories(limit=limit)
        
        return [item['category'] for item in trending_cats if item['category']]

    # Suggested Creator Queries
    @strawberry.field
    def suggested_creators(
        self,
        info: strawberry.types.Info,
        limit: int = 20,
        filter: Optional[SuggestionFilterInput] = None
    ) -> List[RecommendationCreatorType]:
        """Get creator suggestions for current user"""
        user = require_auth(info)
        
        queryset = SuggestedCreator.get_user_suggestions(user, limit=limit)
        
        if filter:
            if filter.seenOnly is not None:
                queryset = queryset.filter(is_seen=filter.seenOnly)
            if filter.reason:
                queryset = queryset.filter(suggestion_reason=filter.reason)
        
        return [RecommendationCreatorType.from_model(suggestion) for suggestion in queryset]

    @strawberry.field
    def suggestion_analytics(
        self,
        info: strawberry.types.Info,
        days: int = 7
    ) -> SuggestionAnalytics:
        """Get suggestion performance analytics"""
        user = require_auth(info)
        
        analytics = SuggestedCreator.get_suggestion_analytics(user, days=days)
        
        return SuggestionAnalytics(
            totalSuggestions=analytics['total_suggestions'],
            seenCount=analytics['seen_count'],
            seenRate=analytics['seen_rate'],
            followedCount=analytics['followed_count'],
            followRate=analytics['follow_rate']
        )

    # User Interest Profile Queries
    @strawberry.field
    def my_interest_profile(self, info: strawberry.types.Info) -> UserInterestProfileType:
        """Get current user's interest profile"""
        user = require_auth(info)
        
        profile = UserInterestProfile.get_or_create_profile(user)
        
        return UserInterestProfileType.from_model(profile)

    @strawberry.field
    def my_top_categories(
        self,
        info: strawberry.types.Info,
        limit: int = 5
    ) -> List[CategoryWeight]:
        """Get user's top preferred categories"""
        user = require_auth(info)
        
        profile = UserInterestProfile.get_or_create_profile(user)
        
        top_categories = profile.get_top_categories(limit)
        
        return [CategoryWeight(category=cat, weight=float(weight)) for cat, weight in top_categories]

    @strawberry.field
    def my_profile_summary(self, info: strawberry.types.Info) -> ProfileSummary:
        """Get summary of user's interest profile"""
        user = require_auth(info)
        
        profile = UserInterestProfile.get_or_create_profile(user)
        summary = profile.get_profile_summary()
        
        # Convert top categories to CategoryWeight objects
        top_categories = [CategoryWeight(category=cat['category'], weight=cat['weight']) for cat in summary['top_categories']]
        
        return ProfileSummary(
            topCategories=top_categories,
            preferredFormats=summary['preferred_formats'],
            purchasePropensity=summary['purchase_propensity'],
            tipPropensity=summary['tip_propensity'],
            avgCompletionRate=summary['avg_completion_rate'],
            profileConfidence=summary['profile_confidence'],
            totalInteractions=summary['total_interactions'],
            lastActive=summary['last_active']
        )

    # Admin Queries
    @strawberry.field
    def platform_interactions(
        self,
        info: strawberry.types.Info,
        interactionType: Optional[str] = None,
        days: int = 30,
        limit: int = 100
    ) -> List[UserInteractionType]:
        """Get all platform interactions (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = UserInteraction.objects.filter(tenant=user.tenant)
        
        if interactionType:
            queryset = queryset.filter(interaction_type=interactionType)
        
        if days:
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(interacted_at__gte=cutoff_date)
        
        interactions = queryset.select_related('user', 'content', 'creator').order_by('-interacted_at')[:limit]
        
        return [UserInteractionType.from_model(item) for item in interactions]

    @strawberry.field
    def platform_interaction_stats(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> PlatformInteractionStats:
        """Get platform interaction statistics (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        interactions = UserInteraction.objects.filter(
            tenant=user.tenant,
            interacted_at__gte=cutoff_date
        )
        
        stats = interactions.values('interaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        by_type = [InteractionTypeStats(interactionType=stat['interaction_type'], count=stat['count']) for stat in stats]
        
        return PlatformInteractionStats(
            periodDays=days,
            totalInteractions=interactions.count(),
            byType=by_type
        )

    @strawberry.field
    def recommendation_performance(
        self,
        info: strawberry.types.Info,
        days: int = 7
    ) -> RecommendationPerformance:
        """Get recommendation system performance (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Feed recommendations
        feed_recs = FeedRecommendation.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        )
        
        feed_total = feed_recs.count()
        feed_seen = feed_recs.filter(is_seen=True).count()
        feed_interacted = feed_recs.filter(is_interacted=True).count()
        
        # Creator suggestions
        creator_suggestions = SuggestedCreator.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        )
        
        creator_total = creator_suggestions.count()
        creator_seen = creator_suggestions.filter(is_seen=True).count()
        creator_followed = creator_suggestions.filter(is_followed=True).count()
        
        return RecommendationPerformance(
            periodDays=days,
            feedRecommendations=FeedRecommendationPerformance(
                total=feed_total,
                seen=feed_seen,
                seenRate=(feed_seen / feed_total * 100) if feed_total > 0 else 0,
                interacted=feed_interacted,
                interactionRate=(feed_interacted / feed_seen * 100) if feed_seen > 0 else 0,
            ),
            creatorSuggestions=CreatorSuggestionPerformance(
                total=creator_total,
                seen=creator_seen,
                seenRate=(creator_seen / creator_total * 100) if creator_total > 0 else 0,
                followed=creator_followed,
                followRate=(creator_followed / creator_seen * 100) if creator_seen > 0 else 0,
            )
        )
