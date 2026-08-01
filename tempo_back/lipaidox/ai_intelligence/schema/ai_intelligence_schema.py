import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import json


@strawberry.scalar
class JSON:
    """Custom JSON scalar for Strawberry GraphQL"""
    @staticmethod
    def serialize(value):
        return json.dumps(value) if value else "{}"
    
    @staticmethod
    def parse_value(value):
        return json.loads(value) if value else {}


from ..models import (
    # AI Intelligence
    AIMediaIntelligence, AIScanStatus, AIDuplicateAction, WatermarkType,
    FingerprintMethod, ReverseScanStatus, ContentWatermark, WatermarkStatus,
    WatermarkPosition, AIScanQueue, QueueJobStatus, QueueJobType,
    
    # Analytics
    CreatorAnalytics, ContentAnalytics, PlatformAnalytics,
    
    # Recommendations
    ContentScore, FeedRecommendation, SuggestedCreator
)


# AI Intelligence Types
@strawberry.type
class AIMediaIntelligenceType:
    id: strawberry.ID
    contentId: strawberry.ID
    mediaId: strawberry.ID
    creatorId: strawberry.ID
    
    # Fingerprinting
    fingerprintMethod: str
    sha256Hash: Optional[str]
    phashHash: Optional[str]
    dhashHash: Optional[str]
    combinedFingerprint: Optional[str]
    fingerprintGeneratedAt: Optional[datetime]
    
    # Duplicate Detection
    isDuplicate: bool
    duplicateOfContentId: Optional[strawberry.ID]
    duplicateOfMediaId: Optional[strawberry.ID]
    duplicateSimilarityScore: Optional[Decimal]
    duplicateAction: str
    duplicateDetectedAt: Optional[datetime]
    
    # Reverse Image Search
    reverseScanStatus: str
    reverseScanMatchesCount: int
    reverseScanResults: str
    reverseScannedAt: Optional[datetime]
    
    # Authenticity
    authenticityScore: Optional[Decimal]
    authenticityNote: Optional[str]
    
    # Price Benchmark
    priceBenchmarkMin: Optional[Decimal]
    priceBenchmarkMax: Optional[Decimal]
    priceBenchmarkAvg: Optional[Decimal]
    priceBenchmarkCurrency: str
    priceBenchmarkedAt: Optional[datetime]
    
    # Overall Status
    scanStatus: str
    scanStartedAt: Optional[datetime]
    scanCompletedAt: Optional[datetime]
    scanError: Optional[str]
    
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: AIMediaIntelligence):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            mediaId=strawberry.ID(str(instance.media_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            fingerprintMethod=instance.fingerprint_method,
            sha256Hash=instance.sha256_hash,
            phashHash=instance.phash_hash,
            dhashHash=instance.dhash_hash,
            combinedFingerprint=instance.combined_fingerprint,
            fingerprintGeneratedAt=instance.fingerprint_generated_at,
            isDuplicate=instance.is_duplicate,
            duplicateOfContentId=strawberry.ID(str(instance.duplicate_of_content_id)) if instance.duplicate_of_content else None,
            duplicateOfMediaId=strawberry.ID(str(instance.duplicate_of_media_id)) if instance.duplicate_of_media else None,
            duplicateSimilarityScore=instance.duplicate_similarity_score,
            duplicateAction=instance.duplicate_action,
            duplicateDetectedAt=instance.duplicate_detected_at,
            reverseScanStatus=instance.reverse_scan_status,
            reverseScanMatchesCount=instance.reverse_scan_matches_count,
            reverseScanResults=json.dumps(instance.reverse_scan_results) if instance.reverse_scan_results else "{}",
            reverseScannedAt=instance.reverse_scanned_at,
            authenticityScore=instance.authenticity_score,
            authenticityNote=instance.authenticity_note,
            priceBenchmarkMin=instance.price_benchmark_min,
            priceBenchmarkMax=instance.price_benchmark_max,
            priceBenchmarkAvg=instance.price_benchmark_avg,
            priceBenchmarkCurrency=instance.price_benchmark_currency,
            priceBenchmarkedAt=instance.price_benchmarked_at,
            scanStatus=instance.scan_status,
            scanStartedAt=instance.scan_started_at,
            scanCompletedAt=instance.scan_completed_at,
            scanError=instance.scan_error,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class ContentWatermarkType:
    id: strawberry.ID
    contentId: strawberry.ID
    mediaId: strawberry.ID
    creatorId: strawberry.ID
    
    # Watermark Type
    watermarkType: str
    
    # Visible Watermark
    visibleEnabled: bool
    visibleText: Optional[str]
    visibleLogoUrl: Optional[str]
    visiblePosition: str
    visibleOpacity: Decimal
    visibleFontSize: int
    visibleColor: str
    watermarkedFileUrl: Optional[str]
    
    # Invisible Watermark
    invisibleEnabled: bool
    invisiblePayload: str
    invisibleMethod: str
    
    # Status
    status: str
    appliedAt: Optional[datetime]
    errorMessage: Optional[str]
    
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: ContentWatermark):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            mediaId=strawberry.ID(str(instance.media_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            watermarkType=instance.watermark_type,
            visibleEnabled=instance.visible_enabled,
            visibleText=instance.visible_text,
            visibleLogoUrl=instance.visible_logo_url,
            visiblePosition=instance.visible_position,
            visibleOpacity=instance.visible_opacity,
            visibleFontSize=instance.visible_font_size,
            visibleColor=instance.visible_color,
            watermarkedFileUrl=instance.watermarked_file_url,
            invisibleEnabled=instance.invisible_enabled,
            invisiblePayload=json.dumps(instance.invisible_payload) if instance.invisible_payload else "{}",
            invisibleMethod=instance.invisible_method,
            status=instance.status,
            appliedAt=instance.applied_at,
            errorMessage=instance.error_message,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class AIScanQueueType:
    id: strawberry.ID
    contentId: strawberry.ID
    mediaId: strawberry.ID
    creatorId: strawberry.ID
    
    jobType: str
    status: str
    priority: int
    attempts: int
    maxAttempts: int
    errorMessage: Optional[str]
    
    queuedAt: datetime
    startedAt: Optional[datetime]
    completedAt: Optional[datetime]
    nextRetryAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: AIScanQueue):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            mediaId=strawberry.ID(str(instance.media_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            jobType=instance.job_type,
            status=instance.status,
            priority=instance.priority,
            attempts=instance.attempts,
            maxAttempts=instance.max_attempts,
            errorMessage=instance.error_message,
            queuedAt=instance.queued_at,
            startedAt=instance.started_at,
            completedAt=instance.completed_at,
            nextRetryAt=instance.next_retry_at,
            createdAt=instance.created_at,
        )


# Analytics Types
@strawberry.type
class CreatorAnalyticsType:
    id: strawberry.ID
    creatorId: strawberry.ID
    periodDate: datetime
    periodType: str
    
    # Audience Metrics
    followerCount: int
    followerGained: int
    followerLost: int
    subscriberCount: int
    subscriberGained: int
    subscriberLost: int
    
    # Content Metrics
    contentPublished: int
    totalContentViews: int
    totalContentLikes: int
    totalContentComments: int
    
    # Revenue Metrics
    revenueFromSubscriptions: Decimal
    revenueFromPPV: Decimal
    revenueFromTips: Decimal
    revenueFromCredits: Decimal
    revenueFromLiveStreams: Decimal
    totalRevenue: Decimal
    platformFeesPaid: Decimal
    netRevenue: Decimal
    
    # Live Streaming Metrics
    liveStreamsCount: int
    liveStreamTotalViewers: int
    liveStreamPeakViewers: int
    liveStreamDurationMins: int
    
    # Engagement Metrics
    engagementRate: Decimal
    ppvPurchaseRate: Decimal
    subscriptionConversionRate: Decimal
    
    computedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorAnalytics):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            periodDate=instance.period_date,
            periodType=instance.period_type,
            followerCount=instance.follower_count,
            followerGained=instance.follower_gained,
            followerLost=instance.follower_lost,
            subscriberCount=instance.subscriber_count,
            subscriberGained=instance.subscriber_gained,
            subscriberLost=instance.subscriber_lost,
            contentPublished=instance.content_published,
            totalContentViews=instance.total_content_views,
            totalContentLikes=instance.total_content_likes,
            totalContentComments=instance.total_content_comments,
            revenueFromSubscriptions=instance.revenue_from_subscriptions,
            revenueFromPPV=instance.revenue_from_ppv,
            revenueFromTips=instance.revenue_from_tips,
            revenueFromCredits=instance.revenue_from_credits,
            revenueFromLiveStreams=instance.revenue_from_live_streams,
            totalRevenue=instance.total_revenue,
            platformFeesPaid=instance.platform_fees_paid,
            netRevenue=instance.net_revenue,
            liveStreamsCount=instance.live_streams_count,
            liveStreamTotalViewers=instance.live_stream_total_viewers,
            liveStreamPeakViewers=instance.live_stream_peak_viewers,
            liveStreamDurationMins=instance.live_stream_duration_mins,
            engagementRate=instance.engagement_rate,
            ppvPurchaseRate=instance.ppv_purchase_rate,
            subscriptionConversionRate=instance.subscription_conversion_rate,
            computedAt=instance.computed_at,
            createdAt=instance.created_at,
        )


@strawberry.type
class ContentAnalyticsType:
    id: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    periodDate: datetime
    periodType: str
    
    # View Metrics
    viewCount: int
    uniqueViewCount: int
    averageWatchDurationS: int
    completionRate: Decimal
    
    # Engagement Metrics
    likeCount: int
    commentCount: int
    shareCount: int
    saveCount: int
    engagementRate: Decimal
    
    # Revenue Metrics
    ppvPurchases: int
    ppvRevenue: Decimal
    tipCount: int
    tipRevenue: Decimal
    totalRevenue: Decimal
    
    # Audience Metrics
    subscriberViews: int
    nonSubscriberViews: int
    newSubscribersFromContent: int
    
    computedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: ContentAnalytics):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            periodDate=instance.period_date,
            periodType=instance.period_type,
            viewCount=instance.view_count,
            uniqueViewCount=instance.unique_view_count,
            averageWatchDurationS=instance.average_watch_duration_s,
            completionRate=instance.completion_rate,
            likeCount=instance.like_count,
            commentCount=instance.comment_count,
            shareCount=instance.share_count,
            saveCount=instance.save_count,
            engagementRate=instance.engagement_rate,
            ppvPurchases=instance.ppv_purchases,
            ppvRevenue=instance.ppv_revenue,
            tipCount=instance.tip_count,
            tipRevenue=instance.tip_revenue,
            totalRevenue=instance.total_revenue,
            subscriberViews=instance.subscriber_views,
            nonSubscriberViews=instance.non_subscriber_views,
            newSubscribersFromContent=instance.new_subscribers_from_content,
            computedAt=instance.computed_at,
            createdAt=instance.created_at,
        )


@strawberry.type
class PlatformAnalyticsType:
    id: strawberry.ID
    periodDate: datetime
    periodType: str
    
    # User Metrics
    totalUsers: int
    newUsers: int
    activeUsers: int
    totalCreators: int
    newCreators: int
    activeCreators: int
    totalFans: int
    newFans: int
    
    # Content Metrics
    totalContentPublished: int
    totalContentViews: int
    totalLiveStreams: int
    
    # Revenue Metrics
    grossRevenue: Decimal
    platformFeesCollected: Decimal
    totalPayouts: Decimal
    totalRefunds: Decimal
    
    # Subscription Metrics
    newSubscriptions: int
    cancelledSubscriptions: int
    activeSubscriptions: int
    
    # Credits Metrics
    creatorCreditsSold: int
    fanCreditsSold: int
    fanCreditsGifted: int
    
    computedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: PlatformAnalytics):
        return cls(
            id=strawberry.ID(str(instance.id)),
            periodDate=instance.period_date,
            periodType=instance.period_type,
            totalUsers=instance.total_users,
            newUsers=instance.new_users,
            activeUsers=instance.active_users,
            totalCreators=instance.total_creators,
            newCreators=instance.new_creators,
            activeCreators=instance.active_creators,
            totalFans=instance.total_fans,
            newFans=instance.new_fans,
            totalContentPublished=instance.total_content_published,
            totalContentViews=instance.total_content_views,
            totalLiveStreams=instance.total_live_streams,
            grossRevenue=instance.gross_revenue,
            platformFeesCollected=instance.platform_fees_collected,
            totalPayouts=instance.total_payouts,
            totalRefunds=instance.total_refunds,
            newSubscriptions=instance.new_subscriptions,
            cancelledSubscriptions=instance.cancelled_subscriptions,
            activeSubscriptions=instance.active_subscriptions,
            creatorCreditsSold=instance.creator_credits_sold,
            fanCreditsSold=instance.fan_credits_sold,
            fanCreditsGifted=instance.fan_credits_gifted,
            computedAt=instance.computed_at,
            createdAt=instance.created_at,
        )


# Recommendation Types
@strawberry.type
class ContentScoreType:
    id: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    
    # Score Components
    recencyScore: Decimal
    engagementScore: Decimal
    purchaseRateScore: Decimal
    creatorTierScore: Decimal
    velocityScore: Decimal
    
    # Overall Score
    overallScore: Decimal
    scoreRank: int
    
    # Trending Metrics
    trendingScore: Decimal
    isTrending: bool
    trendPosition: int
    
    # Category Performance
    categoryScore: Decimal
    categoryRank: int
    
    # Quality Metrics
    qualityScore: Decimal
    aiAuthenticityScore: Decimal
    
    lastCalculatedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: ContentScore):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            recencyScore=instance.recency_score,
            engagementScore=instance.engagement_score,
            purchaseRateScore=instance.purchase_rate_score,
            creatorTierScore=instance.creator_tier_score,
            velocityScore=instance.velocity_score,
            overallScore=instance.overall_score,
            scoreRank=instance.score_rank,
            trendingScore=instance.trending_score,
            isTrending=instance.is_trending,
            trendPosition=instance.trend_position,
            categoryScore=instance.category_score,
            categoryRank=instance.category_rank,
            qualityScore=instance.quality_score,
            aiAuthenticityScore=instance.ai_authenticity_score,
            lastCalculatedAt=instance.last_calculated_at,
            createdAt=instance.created_at,
        )


@strawberry.type
class FeedRecommendationType:
    id: strawberry.ID
    userId: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    
    # Recommendation Scores
    relevanceScore: Decimal
    interestMatchScore: Decimal
    socialScore: Decimal
    diversityScore: Decimal
    freshnessScore: Decimal
    
    # Overall Score
    recommendationScore: Decimal
    feedPosition: int
    
    # Context
    recommendationReason: Optional[str]
    weightFactors: str
    
    # Interactions
    shownAt: Optional[datetime]
    viewedAt: Optional[datetime]
    likedAt: Optional[datetime]
    sharedAt: Optional[datetime]
    purchasedAt: Optional[datetime]
    skippedAt: Optional[datetime]
    
    # Feedback
    userFeedback: int
    engagementTimeSeconds: int
    
    generatedAt: datetime
    updatedAt: datetime
    expiresAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: FeedRecommendation):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            relevanceScore=instance.relevance_score,
            interestMatchScore=instance.interest_match_score,
            socialScore=instance.social_score,
            diversityScore=instance.diversity_score,
            freshnessScore=instance.freshness_score,
            recommendationScore=instance.recommendation_score,
            feedPosition=instance.feed_position,
            recommendationReason=instance.recommendation_reason,
            weightFactors=json.dumps(instance.weight_factors) if instance.weight_factors else "{}",
            shownAt=instance.shown_at,
            viewedAt=instance.viewed_at,
            likedAt=instance.liked_at,
            sharedAt=instance.shared_at,
            purchasedAt=instance.purchased_at,
            skippedAt=instance.skipped_at,
            userFeedback=instance.user_feedback,
            engagementTimeSeconds=instance.engagement_time_seconds,
            generatedAt=instance.generated_at,
            updatedAt=instance.updated_at,
            expiresAt=instance.expires_at,
        )


@strawberry.type
class SuggestedCreatorType:
    id: strawberry.ID
    userId: strawberry.ID
    suggestedCreatorId: strawberry.ID
    
    # Recommendation Scores
    categoryMatchScore: Decimal
    popularityScore: Decimal
    compatibilityScore: Decimal
    growthScore: Decimal
    
    # Overall Score
    suggestionScore: Decimal
    suggestionRank: int
    
    # Context
    suggestionReasons: str
    matchingCategories: str
    
    # Interactions
    shownAt: Optional[datetime]
    viewedAt: Optional[datetime]
    followedAt: Optional[datetime]
    subscribedAt: Optional[datetime]
    dismissedAt: Optional[datetime]
    
    # Feedback
    userFeedback: int
    
    generatedAt: datetime
    updatedAt: datetime
    expiresAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: SuggestedCreator):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            suggestedCreatorId=strawberry.ID(str(instance.suggested_creator_id)),
            categoryMatchScore=instance.category_match_score,
            popularityScore=instance.popularity_score,
            compatibilityScore=instance.compatibility_score,
            growthScore=instance.growth_score,
            suggestionScore=instance.suggestion_score,
            suggestionRank=instance.suggestion_rank,
            suggestionReasons=json.dumps(instance.suggestion_reasons) if instance.suggestion_reasons else "[]",
            matchingCategories=json.dumps(instance.matching_categories) if instance.matching_categories else "[]",
            shownAt=instance.shown_at,
            viewedAt=instance.viewed_at,
            followedAt=instance.followed_at,
            subscribedAt=instance.subscribed_at,
            dismissedAt=instance.dismissed_at,
            userFeedback=instance.user_feedback,
            generatedAt=instance.generated_at,
            updatedAt=instance.updated_at,
            expiresAt=instance.expires_at,
        )


# Input Types
@strawberry.input
class AnalyticsPeriodInput:
    periodType: str = "daily"
    dateFrom: Optional[datetime] = None
    dateTo: Optional[datetime] = None


@strawberry.input
class RecommendationFilterInput:
    contentType: Optional[str] = None
    categories: Optional[List[str]] = None
    minScore: Optional[Decimal] = None
    maxScore: Optional[Decimal] = None


@strawberry.input
class AIScanInput:
    contentId: strawberry.ID
    scanTypes: List[str] = strawberry.field(default_factory=lambda: ["full_pipeline"])
    priority: int = 5


# Summary Types
@strawberry.type
class AnalyticsPeriodSummary:
    revenue: float
    views: int
    likes: int
    avgEngagementRate: float
    newSubscribers: int


@strawberry.type
class CurrentStats:
    followers: int
    subscribers: int
    contentCount: int


@strawberry.type
class MyAnalyticsSummary:
    last30Days: AnalyticsPeriodSummary
    current: CurrentStats


@strawberry.type
class PlatformSummaryPeriod:
    revenue: float
    newUsers: int
    newCreators: int
    contentPublished: int
    totalViews: int


@strawberry.type
class PlatformCurrentStats:
    totalUsers: int
    totalCreators: int
    totalContent: int


@strawberry.type
class PlatformSummary:
    last30Days: PlatformSummaryPeriod
    current: PlatformCurrentStats
