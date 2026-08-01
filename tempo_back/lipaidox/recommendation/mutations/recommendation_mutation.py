import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone

from ..models import (
    UserInteraction, InteractionType,
    ContentScore,
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
    RecordInteractionInput
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
class RecommendationMutation:
    # User Interaction Mutations
    @strawberry.mutation
    def record_interaction(self, info: strawberry.types.Info, input: RecordInteractionInput) -> UserInteractionType:
        """Record a user interaction"""
        user = require_auth(info)
        
        # Get content and creator objects
        content = None
        creator = None
        
        if input.contentId:
            from lipaidox.content.models import Content
            try:
                content = Content.objects.get(id=input.contentId, tenant=user.tenant)
                creator = content.creator
            except Content.DoesNotExist:
                raise Exception("Content not found")
        elif input.creatorId:
            from lipaidox.creator_profile.models import CreatorProfile
            try:
                creator = CreatorProfile.objects.get(id=input.creatorId, tenant=user.tenant)
            except CreatorProfile.DoesNotExist:
                raise Exception("Creator not found")
        
        # Record interaction
        interaction = UserInteraction.record_interaction(
            user=user,
            interaction_type=input.interactionType,
            content=content,
            creator=creator,
            watch_duration_s=input.watchDurationS,
            completion_rate=input.completionRate,
            source=input.source,
            device_type=input.deviceType,
            session_id=input.sessionId
        )
        
        # Update user interest profile asynchronously
        try:
            profile = UserInterestProfile.get_or_create_profile(user)
            profile.compute_profile()
        except Exception:
            pass  # Don't fail the interaction if profile update fails
        
        return UserInteractionType.from_model(interaction)

    @strawberry.mutation
    def record_view(self, info: strawberry.types.Info, contentId: strawberry.ID, watchDurationS: Optional[int] = None, completionRate: Optional[float] = None) -> UserInteractionType:
        """Record a content view"""
        user = require_auth(info)
        
        from lipaidox.content.models import Content
        try:
            content = Content.objects.get(id=contentId, tenant=user.tenant)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        interaction = UserInteraction.record_view(
            user=user,
            content=content,
            watch_duration=watchDurationS,
            completion_rate=completionRate
        )
        
        return UserInteractionType.from_model(interaction)

    @strawberry.mutation
    def record_like(self, info: strawberry.types.Info, contentId: strawberry.ID) -> UserInteractionType:
        """Record a content like"""
        user = require_auth(info)
        
        from lipaidox.content.models import Content
        try:
            content = Content.objects.get(id=contentId, tenant=user.tenant)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        interaction = UserInteraction.record_like(user=user, content=content)
        
        return UserInteractionType.from_model(interaction)

    @strawberry.mutation
    def record_purchase(self, info: strawberry.types.Info, contentId: strawberry.ID, source: Optional[str] = None) -> UserInteractionType:
        """Record a content purchase"""
        user = require_auth(info)
        
        from lipaidox.content.models import Content
        try:
            content = Content.objects.get(id=contentId, tenant=user.tenant)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        interaction = UserInteraction.record_purchase(
            user=user,
            content=content,
            source=source
        )
        
        return UserInteractionType.from_model(interaction)

    @strawberry.mutation
    def record_follow(self, info: strawberry.types.Info, creatorId: strawberry.ID, source: Optional[str] = None) -> UserInteractionType:
        """Record a creator follow"""
        user = require_auth(info)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            creator = CreatorProfile.objects.get(id=creatorId, tenant=user.tenant)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator not found")
        
        interaction = UserInteraction.record_follow(
            user=user,
            creator=creator,
            source=source
        )
        
        return UserInteractionType.from_model(interaction)

    # Content Score Mutations
    @strawberry.mutation
    def update_content_score(self, info: strawberry.types.Info, contentId: strawberry.ID) -> ContentScoreType:
        """Update content score (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        from lipaidox.content.models import Content
        try:
            content = Content.objects.get(id=contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        # Get or create score
        score, created = ContentScore.objects.get_or_create(
            content=content,
            creator=content.creator,
            tenant=content.tenant
        )
        
        # Update raw metrics
        score.update_raw_metrics()
        
        # Calculate scores
        score.recency_score = score.calculate_recency_score()
        score.engagement_score = score.calculate_engagement_score()
        score.purchase_score = score.calculate_purchase_score()
        score.creator_tier_score = score.calculate_creator_tier_score()
        score.velocity_score = score.calculate_velocity_score()
        score.calculate_total_score()
        
        return ContentScoreType.from_model(score)

    @strawberry.mutation
    def calculate_all_scores(self, info: strawberry.types.Info) -> str:
        """Calculate scores for all content (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        ContentScore.calculate_all_scores()
        
        return "Content scores calculation completed"

    # Feed Recommendation Mutations
    @strawberry.mutation
    def regenerate_my_feed(self, info: strawberry.types.Info) -> List[RecommendationFeedType]:
        """Regenerate user's personalized feed"""
        user = require_auth(info)
        
        recommendations = FeedRecommendation.generate_user_feed(user, limit=50)
        
        return [RecommendationFeedType.from_model(rec) for rec in recommendations]

    @strawberry.mutation
    def mark_feed_seen(self, info: strawberry.types.Info, recommendationId: strawberry.ID) -> RecommendationFeedType:
        """Mark feed recommendation as seen"""
        user = require_auth(info)
        
        try:
            recommendation = FeedRecommendation.objects.get(
                id=recommendationId,
                user=user
            )
        except FeedRecommendation.DoesNotExist:
            raise Exception("Recommendation not found")
        
        recommendation.mark_seen()
        
        return RecommendationFeedType.from_model(recommendation)

    @strawberry.mutation
    def mark_feed_interacted(self, info: strawberry.types.Info, recommendationId: strawberry.ID) -> RecommendationFeedType:
        """Mark feed recommendation as interacted"""
        user = require_auth(info)
        
        try:
            recommendation = FeedRecommendation.objects.get(
                id=recommendationId,
                user=user
            )
        except FeedRecommendation.DoesNotExist:
            raise Exception("Recommendation not found")
        
        recommendation.mark_interacted()
        
        return RecommendationFeedType.from_model(recommendation)

    # Trending Content Mutations
    @strawberry.mutation
    def update_trending_content(self, info: strawberry.types.Info, windowHours: int = 24, limit: int = 50) -> str:
        """Update trending content (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        TrendingContent.update_trending_content(
            window_hours=windowHours,
            limit=limit
        )
        
        return f"Trending content updated for {windowHours}h window"

    @strawberry.mutation
    def cleanup_expired_trending(self, info: strawberry.types.Info) -> str:
        """Clean up expired trending entries (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        deleted_count = TrendingContent.cleanup_expired_entries()
        
        return f"Cleaned up {deleted_count} expired trending entries"

    # Suggested Creator Mutations
    @strawberry.mutation
    def regenerate_suggestions(self, info: strawberry.types.Info) -> List[RecommendationCreatorType]:
        """Regenerate creator suggestions for user"""
        user = require_auth(info)
        
        suggestions = SuggestedCreator.generate_user_suggestions(user, limit=20)
        
        return [RecommendationCreatorType.from_model(suggestion) for suggestion in suggestions]

    @strawberry.mutation
    def mark_suggestion_seen(self, info: strawberry.types.Info, suggestionId: strawberry.ID) -> RecommendationCreatorType:
        """Mark creator suggestion as seen"""
        user = require_auth(info)
        
        try:
            suggestion = SuggestedCreator.objects.get(
                id=suggestionId,
                user=user
            )
        except SuggestedCreator.DoesNotExist:
            raise Exception("Suggestion not found")
        
        suggestion.mark_seen()
        
        return RecommendationCreatorType.from_model(suggestion)

    @strawberry.mutation
    def mark_suggestion_followed(self, info: strawberry.types.Info, suggestionId: strawberry.ID) -> RecommendationCreatorType:
        """Mark creator suggestion as followed"""
        user = require_auth(info)
        
        try:
            suggestion = SuggestedCreator.objects.get(
                id=suggestionId,
                user=user
            )
        except SuggestedCreator.DoesNotExist:
            raise Exception("Suggestion not found")
        
        suggestion.mark_followed()
        
        return RecommendationCreatorType.from_model(suggestion)

    @strawberry.mutation
    def cleanup_expired_suggestions(self, info: strawberry.types.Info) -> str:
        """Clean up expired suggestions (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        deleted_count = SuggestedCreator.cleanup_expired_suggestions()
        
        return f"Cleaned up {deleted_count} expired suggestions"

    # User Interest Profile Mutations
    @strawberry.mutation
    def update_my_interest_profile(self, info: strawberry.types.Info) -> UserInterestProfileType:
        """Update current user's interest profile"""
        user = require_auth(info)
        
        profile = UserInterestProfile.get_or_create_profile(user)
        profile.compute_profile()
        
        return UserInterestProfileType.from_model(profile)

    @strawberry.mutation
    def compute_all_profiles(self, info: strawberry.types.Info) -> str:
        """Compute profiles for all users (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        UserInterestProfile.compute_all_profiles()
        
        return "All user interest profiles computed"

    # Batch Operations (Admin Only)
    @strawberry.mutation
    def batch_record_interactions(self, info: strawberry.types.Info, interactions: List[RecordInteractionInput]) -> List[UserInteractionType]:
        """Record multiple interactions (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        recorded_interactions = []
        
        with transaction.atomic():
            for interaction_input in interactions:
                try:
                    # Get content and creator objects
                    content = None
                    creator = None
                    
                    if interaction_input.contentId:
                        from lipaidox.content.models import Content
                        try:
                            content = Content.objects.get(id=interaction_input.contentId)
                            creator = content.creator
                        except Content.DoesNotExist:
                            continue
                    
                    # Record interaction
                    interaction = UserInteraction.record_interaction(
                        user=user,
                        interaction_type=interaction_input.interactionType,
                        content=content,
                        creator=creator,
                        watch_duration_s=interaction_input.watchDurationS,
                        completion_rate=interaction_input.completionRate,
                        source=interaction_input.source,
                        device_type=interaction_input.deviceType,
                        session_id=interaction_input.sessionId
                    )
                    
                    recorded_interactions.append(UserInteractionType.from_model(interaction))
                    
                except Exception:
                    continue  # Skip failed interactions
        
        return recorded_interactions
