import strawberry
from typing import Optional, List
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta, date

from ..models import (
    # AI Intelligence
    AIMediaIntelligence, ContentWatermark, AIScanQueue,
    
    # Analytics
    CreatorAnalytics, ContentAnalytics, PlatformAnalytics,
    
    # Recommendations
    ContentScore, FeedRecommendation, SuggestedCreator
)

from ..schema.ai_intelligence_schema import (
    # AI Intelligence Types
    AIMediaIntelligenceType, ContentWatermarkType, AIScanQueueType,
    
    # Analytics Types
    CreatorAnalyticsType, ContentAnalyticsType, PlatformAnalyticsType,
    
    # Recommendation Types
    ContentScoreType, FeedRecommendationType, SuggestedCreatorType,
    
    # Input Types
    AnalyticsPeriodInput, RecommendationFilterInput, AIScanInput,
    
    # Summary Types
    MyAnalyticsSummary, PlatformSummary, AnalyticsPeriodSummary, 
    CurrentStats, PlatformSummaryPeriod, PlatformCurrentStats
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
class AIIntelligenceQuery:
    # AI Intelligence Queries
    @strawberry.field
    def content_ai_intelligence(self, info: strawberry.types.Info, contentId: strawberry.ID) -> Optional[AIMediaIntelligenceType]:
        """Get AI intelligence data for specific content"""
        user = require_auth(info)
        
        try:
            ai_data = AIMediaIntelligence.objects.get(
                content_id=contentId,
                tenant=user.tenant
            )
            return AIMediaIntelligenceType.from_model(ai_data)
        except AIMediaIntelligence.DoesNotExist:
            return None

    @strawberry.field
    def my_content_ai_intelligence(self, info: strawberry.types.Info, limit: int = 50) -> List[AIMediaIntelligenceType]:
        """Get AI intelligence data for current user's content"""
        user = require_auth(info)
        
        if not hasattr(user, 'creator_profile'):
            return []
        
        ai_data = AIMediaIntelligence.objects.filter(
            creator=user.creator_profile,
            tenant=user.tenant
        ).select_related('content', 'media').order_by('-created_at')[:limit]
        
        return [AIMediaIntelligenceType.from_model(item) for item in ai_data]

    @strawberry.field
    def content_watermarks(self, info: strawberry.types.Info, contentId: strawberry.ID) -> Optional[ContentWatermarkType]:
        """Get watermark data for specific content"""
        user = require_auth(info)
        
        try:
            watermark = ContentWatermark.objects.get(
                content_id=contentId,
                tenant=user.tenant
            )
            return ContentWatermarkType.from_model(watermark)
        except ContentWatermark.DoesNotExist:
            return None

    @strawberry.field
    def ai_scan_queue(self, info: strawberry.types.Info, status: Optional[str] = None) -> List[AIScanQueueType]:
        """Get AI scan queue (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = AIScanQueue.objects.filter(tenant=user.tenant)
        
        if status:
            queryset = queryset.filter(status=status)
        
        queue_items = queryset.select_related('content', 'media', 'creator').order_by('-queued_at')[:100]
        
        return [AIScanQueueType.from_model(item) for item in queue_items]

    # Analytics Queries
    @strawberry.field
    def my_creator_analytics(
        self,
        info: strawberry.types.Info,
        period: AnalyticsPeriodInput = None
    ) -> List[CreatorAnalyticsType]:
        """Get analytics for current creator"""
        user = require_auth(info)
        
        if not hasattr(user, 'creator_profile'):
            return []
        
        if not period:
            period = AnalyticsPeriodInput()
        
        queryset = CreatorAnalytics.objects.filter(
            creator=user.creator_profile,
            tenant=user.tenant,
            period_type=period.periodType
        )
        
        if period.dateFrom:
            queryset = queryset.filter(period_date__gte=period.dateFrom.date())
        if period.dateTo:
            queryset = queryset.filter(period_date__lte=period.dateTo.date())
        
        analytics = queryset.order_by('-period_date')[:90]  # Last 90 periods
        
        return [CreatorAnalyticsType.from_model(item) for item in analytics]

    @strawberry.field
    def content_analytics(
        self,
        info: strawberry.types.Info,
        contentId: strawberry.ID,
        period: AnalyticsPeriodInput = None
    ) -> List[ContentAnalyticsType]:
        """Get analytics for specific content"""
        user = require_auth(info)
        
        if not period:
            period = AnalyticsPeriodInput()
        
        queryset = ContentAnalytics.objects.filter(
            content_id=contentId,
            tenant=user.tenant,
            period_type=period.periodType
        )
        
        if period.dateFrom:
            queryset = queryset.filter(period_date__gte=period.dateFrom.date())
        if period.dateTo:
            queryset = queryset.filter(period_date__lte=period.dateTo.date())
        
        analytics = queryset.order_by('-period_date')[:90]
        
        return [ContentAnalyticsType.from_model(item) for item in analytics]

    @strawberry.field
    def my_content_analytics(
        self,
        info: strawberry.types.Info,
        period: AnalyticsPeriodInput = None,
        limit: int = 50
    ) -> List[ContentAnalyticsType]:
        """Get analytics for current user's content"""
        user = require_auth(info)
        
        if not hasattr(user, 'creator_profile'):
            return []
        
        if not period:
            period = AnalyticsPeriodInput()
        
        queryset = ContentAnalytics.objects.filter(
            creator=user.creator_profile,
            tenant=user.tenant,
            period_type=period.periodType
        )
        
        if period.dateFrom:
            queryset = queryset.filter(period_date__gte=period.dateFrom.date())
        if period.dateTo:
            queryset = queryset.filter(period_date__lte=period.dateTo.date())
        
        analytics = queryset.select_related('content').order_by('-period_date', '-total_revenue')[:limit]
        
        return [ContentAnalyticsType.from_model(item) for item in analytics]

    @strawberry.field
    def platform_analytics(
        self,
        info: strawberry.types.Info,
        period: AnalyticsPeriodInput = None
    ) -> List[PlatformAnalyticsType]:
        """Get platform analytics (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        if not period:
            period = AnalyticsPeriodInput()
        
        queryset = PlatformAnalytics.objects.filter(
            period_type=period.periodType
        )
        
        if period.dateFrom:
            queryset = queryset.filter(period_date__gte=period.dateFrom.date())
        if period.dateTo:
            queryset = queryset.filter(period_date__lte=period.dateTo.date())
        
        analytics = queryset.order_by('-period_date')[:90]
        
        return [PlatformAnalyticsType.from_model(item) for item in analytics]

    # Recommendation Queries
    @strawberry.field
    def my_feed(
        self,
        info: strawberry.types.Info,
        limit: int = 50,
        filter: Optional[RecommendationFilterInput] = None
    ) -> List[FeedRecommendationType]:
        """Get personalized feed for current user"""
        user = require_auth(info)
        
        # Get or generate feed recommendations
        recommendations = FeedRecommendation.get_user_feed(user, limit)
        
        # Apply filters if provided
        if filter:
            if filter.minScore:
                recommendations = [r for r in recommendations if r.recommendation_score >= filter.minScore]
            if filter.maxScore:
                recommendations = [r for r in recommendations if r.recommendation_score <= filter.maxScore]
            if filter.categories:
                recommendations = [r for r in recommendations if r.content.category in filter.categories]
        
        return [FeedRecommendationType.from_model(rec) for rec in recommendations[:limit]]

    @strawberry.field
    def trending_content(self, info: strawberry.types.Info, limit: int = 50) -> List[ContentScoreType]:
        """Get trending content"""
        user = require_auth(info)
        
        trending = ContentScore.get_trending_content(limit)
        
        return [ContentScoreType.from_model(score) for score in trending]

    @strawberry.field
    def top_content(self, info: strawberry.types.Info, limit: int = 100) -> List[ContentScoreType]:
        """Get top scoring content"""
        user = require_auth(info)
        
        top_content = ContentScore.get_top_content(limit)
        
        return [ContentScoreType.from_model(score) for score in top_content]

    @strawberry.field
    def suggested_creators(self, info: strawberry.types.Info, limit: int = 20) -> List[SuggestedCreatorType]:
        """Get creator suggestions for current user"""
        user = require_auth(info)
        
        suggestions = SuggestedCreator.get_user_suggestions(user, limit)
        
        return [SuggestedCreatorType.from_model(suggestion) for suggestion in suggestions]

    @strawberry.field
    def content_scores(
        self,
        info: strawberry.types.Info,
        contentId: Optional[strawberry.ID] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 50
    ) -> List[ContentScoreType]:
        """Get content scores"""
        user = require_auth(info)
        
        queryset = ContentScore.objects.filter(tenant=user.tenant)
        
        if contentId:
            queryset = queryset.filter(content_id=contentId)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)
        
        scores = queryset.select_related('content', 'creator').order_by('-overall_score')[:limit]
        
        return [ContentScoreType.from_model(score) for score in scores]

    # Summary Queries
    @strawberry.field
    def my_analytics_summary(self, info: strawberry.types.Info) -> MyAnalyticsSummary:
        """Get analytics summary for current creator"""
        user = require_auth(info)
        
        if not hasattr(user, 'creator_profile'):
            # Return empty summary for non-creators
            return MyAnalyticsSummary(
                last30Days=AnalyticsPeriodSummary(
                    revenue=0.0,
                    views=0,
                    likes=0,
                    avgEngagementRate=0.0,
                    newSubscribers=0
                ),
                current=CurrentStats(
                    followers=0,
                    subscribers=0,
                    contentCount=0
                )
            )
        
        from django.db.models import Sum, Avg, Count
        
        # Get last 30 days of analytics
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        creator_analytics = CreatorAnalytics.objects.filter(
            creator=user.creator_profile,
            period_date__gte=thirty_days_ago,
            period_type='daily'
        ).aggregate(
            total_revenue=Sum('total_revenue'),
            total_views=Sum('total_content_views'),
            total_likes=Sum('total_content_likes'),
            avg_engagement=Avg('engagement_rate'),
            total_subscribers_gained=Sum('subscriber_gained')
        )
        
        # Get current stats
        current_stats = CurrentStats(
            followers=user.creator_profile.followers.count(),
            subscribers=user.creator_profile.subscribers.filter(is_active=True).count(),
            contentCount=user.creator_profile.content_set.count()
        )
        
        last_30_days = AnalyticsPeriodSummary(
            revenue=float(creator_analytics['total_revenue'] or 0),
            views=creator_analytics['total_views'] or 0,
            likes=creator_analytics['total_likes'] or 0,
            avgEngagementRate=float(creator_analytics['avg_engagement'] or 0),
            newSubscribers=creator_analytics['total_subscribers_gained'] or 0
        )
        
        return MyAnalyticsSummary(
            last30Days=last_30_days,
            current=current_stats
        )

    @strawberry.field
    def platform_summary(self, info: strawberry.types.Info) -> PlatformSummary:
        """Get platform summary (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        from django.contrib.auth import get_user_model
        from lipaidox.creator_profile.models import CreatorProfile
        
        User = get_user_model()
        
        # Get last 30 days of platform analytics
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        platform_analytics = PlatformAnalytics.objects.filter(
            period_date__gte=thirty_days_ago,
            period_type='daily'
        ).aggregate(
            total_revenue=Sum('gross_revenue'),
            total_users_gained=Sum('new_users'),
            total_creators_gained=Sum('new_creators'),
            total_content_published=Sum('total_content_published'),
            total_views=Sum('total_content_views')
        )
        
        # Get current stats
        current_stats = PlatformCurrentStats(
            totalUsers=User.objects.filter(is_active=True).count(),
            totalCreators=CreatorProfile.objects.filter(user__is_active=True).count(),
            totalContent=user.creator_profile.content_set.count() if hasattr(user, 'creator_profile') else 0
        )
        
        last_30_days = PlatformSummaryPeriod(
            revenue=float(platform_analytics['total_revenue'] or 0),
            newUsers=platform_analytics['total_users_gained'] or 0,
            newCreators=platform_analytics['total_creators_gained'] or 0,
            contentPublished=platform_analytics['total_content_published'] or 0,
            totalViews=platform_analytics['total_views'] or 0
        )
        
        return PlatformSummary(
            last30Days=last_30_days,
            current=current_stats
        )
