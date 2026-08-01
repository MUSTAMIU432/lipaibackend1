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
    UserInteraction, InteractionType,
    ContentScore, AudienceType,
    FeedRecommendation, RecommendationReason,
    TrendingContent,
    SuggestedCreator, SuggestionReason,
    UserInterestProfile
)


# User Interaction Types
@strawberry.type
class UserInteractionType:
    id: strawberry.ID
    userId: strawberry.ID
    contentId: Optional[strawberry.ID]
    creatorId: Optional[strawberry.ID]
    interactionType: str
    
    # Context
    watchDurationS: Optional[int]
    completionRate: Optional[Decimal]
    source: Optional[str]
    deviceType: Optional[str]
    sessionId: Optional[str]
    
    # Timestamps
    interactedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: UserInteraction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            contentId=strawberry.ID(str(instance.content_id)) if instance.content else None,
            creatorId=strawberry.ID(str(instance.creator_id)) if instance.creator else None,
            interactionType=instance.interaction_type,
            watchDurationS=instance.watch_duration_s,
            completionRate=instance.completion_rate,
            source=instance.source,
            deviceType=instance.device_type,
            sessionId=instance.session_id,
            interactedAt=instance.interacted_at,
            createdAt=instance.created_at,
        )


# Content Score Types
@strawberry.type
class ContentScoreType:
    id: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    
    # Score Components
    recencyScore: Decimal
    engagementScore: Decimal
    purchaseScore: Decimal
    creatorTierScore: Decimal
    velocityScore: Decimal
    
    # Final Score
    totalScore: Decimal
    
    # Raw Metrics
    viewCount: int
    likeCount: int
    commentCount: int
    shareCount: int
    purchaseCount: int
    engagementRate: Decimal
    
    # Category
    primaryCategory: Optional[str]
    audienceType: str
    
    # Timestamps
    lastComputedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: ContentScore):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            recencyScore=instance.recency_score,
            engagementScore=instance.engagement_score,
            purchaseScore=instance.purchase_score,
            creatorTierScore=instance.creator_tier_score,
            velocityScore=instance.velocity_score,
            totalScore=instance.total_score,
            viewCount=instance.view_count,
            likeCount=instance.like_count,
            commentCount=instance.comment_count,
            shareCount=instance.share_count,
            purchaseCount=instance.purchase_count,
            engagementRate=instance.engagement_rate,
            primaryCategory=instance.primary_category,
            audienceType=instance.audience_type,
            lastComputedAt=instance.last_computed_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


# Feed Recommendation Types
@strawberry.type
class RecommendationFeedType:
    id: strawberry.ID
    userId: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    
    # Recommendation Detail
    recommendationScore: Decimal
    recommendationReason: str
    position: int
    isSeen: bool
    isInteracted: bool
    seenAt: Optional[datetime]
    
    # Validity
    validUntil: datetime
    
    # Timestamps
    computedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: FeedRecommendation):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            recommendationScore=instance.recommendation_score,
            recommendationReason=instance.recommendation_reason,
            position=instance.position,
            isSeen=instance.is_seen,
            isInteracted=instance.is_interacted,
            seenAt=instance.seen_at,
            validUntil=instance.valid_until,
            computedAt=instance.computed_at,
            createdAt=instance.created_at,
        )


# Trending Content Types
@strawberry.type
class TrendingContentType:
    id: strawberry.ID
    contentId: strawberry.ID
    creatorId: strawberry.ID
    trendingScore: Decimal
    rankPosition: int
    category: Optional[str]
    audienceType: str
    trendWindowHours: int
    computedAt: datetime
    expiresAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: TrendingContent):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            trendingScore=instance.trending_score,
            rankPosition=instance.rank_position,
            category=instance.category,
            audienceType=instance.audience_type,
            trendWindowHours=instance.trend_window_hours,
            computedAt=instance.computed_at,
            expiresAt=instance.expires_at,
            createdAt=instance.created_at,
        )


# Suggested Creator Types
@strawberry.type
class RecommendationCreatorType:
    id: strawberry.ID
    userId: strawberry.ID
    creatorId: strawberry.ID
    suggestionScore: Decimal
    rankPosition: int
    suggestionReason: str
    isSeen: bool
    isFollowed: bool
    validUntil: datetime
    computedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: SuggestedCreator):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            suggestionScore=instance.suggestion_score,
            rankPosition=instance.rank_position,
            suggestionReason=instance.suggestion_reason,
            isSeen=instance.is_seen,
            isFollowed=instance.is_followed,
            validUntil=instance.valid_until,
            computedAt=instance.computed_at,
            createdAt=instance.created_at,
        )


# User Interest Profile Types
@strawberry.type
class UserInterestProfileType:
    id: strawberry.ID
    userId: strawberry.ID
    
    # Category Weights
    categoryWeights: str
    
    # Behaviour Signals
    preferredContentFormats: str
    preferredAccessTypes: str
    avgWatchCompletionRate: Decimal
    purchasePropensityScore: Decimal
    tipPropensityScore: Decimal
    
    # Activity
    totalInteractions: int
    lastActiveAt: Optional[datetime]
    profileConfidenceScore: Decimal
    
    # Timestamps
    lastComputedAt: datetime
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: UserInterestProfile):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            categoryWeights=instance.category_weights,
            preferredContentFormats=instance.preferred_content_formats,
            preferredAccessTypes=instance.preferred_access_types,
            avgWatchCompletionRate=instance.avg_watch_completion_rate,
            purchasePropensityScore=instance.purchase_propensity_score,
            tipPropensityScore=instance.tip_propensity_score,
            totalInteractions=instance.total_interactions,
            lastActiveAt=instance.last_active_at,
            profileConfidenceScore=instance.profile_confidence_score,
            lastComputedAt=instance.last_computed_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


# Input Types
@strawberry.input
class RecordInteractionInput:
    contentId: Optional[strawberry.ID]
    creatorId: Optional[strawberry.ID]
    interactionType: str
    watchDurationS: Optional[int]
    completionRate: Optional[Decimal]
    source: Optional[str]
    deviceType: Optional[str]
    sessionId: Optional[str]


@strawberry.input
class RecommendationFilterInput:
    category: Optional[str] = None
    audienceType: Optional[str] = None
    minScore: Optional[Decimal] = None
    maxScore: Optional[Decimal] = None
    seenOnly: Optional[bool] = None


@strawberry.input
class TrendingFilterInput:
    category: Optional[str] = None
    audienceType: Optional[str] = None
    trendWindowHours: Optional[int] = 24


@strawberry.input
class SuggestionFilterInput:
    seenOnly: Optional[bool] = None
    reason: Optional[str] = None


# Analytics Types
@strawberry.type
class FeedAnalytics:
    totalRecommendations: int
    seenCount: int
    seenRate: float
    interactedCount: int
    interactionRate: float


@strawberry.type
class SuggestionAnalytics:
    totalSuggestions: int
    seenCount: int
    seenRate: float
    followedCount: int
    followRate: float


@strawberry.type
class CategoryWeight:
    category: str
    weight: float


@strawberry.type
class ProfileSummary:
    topCategories: List[CategoryWeight]
    preferredFormats: List[str]
    purchasePropensity: float
    tipPropensity: float
    avgCompletionRate: float
    profileConfidence: float
    totalInteractions: int
    lastActive: Optional[str]


@strawberry.type
class InteractionTypeStats:
    interactionType: str
    count: int


@strawberry.type
class PlatformInteractionStats:
    periodDays: int
    totalInteractions: int
    byType: List[InteractionTypeStats]


@strawberry.type
class FeedRecommendationPerformance:
    total: int
    seen: int
    seenRate: float
    interacted: int
    interactionRate: float


@strawberry.type
class CreatorSuggestionPerformance:
    total: int
    seen: int
    seenRate: float
    followed: int
    followRate: float


@strawberry.type
class RecommendationPerformance:
    periodDays: int
    feedRecommendations: FeedRecommendationPerformance
    creatorSuggestions: CreatorSuggestionPerformance
