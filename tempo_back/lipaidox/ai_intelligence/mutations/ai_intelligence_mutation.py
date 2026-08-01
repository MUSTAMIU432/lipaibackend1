import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone

from ..models import (
    # AI Intelligence
    AIMediaIntelligence, ContentWatermark, AIScanQueue,
    
    # Analytics
    CreatorAnalytics, ContentAnalytics, PlatformAnalytics,
    
    # Recommendations
    ContentScore, FeedRecommendation, SuggestedCreator
)

from ..schema.ai_intelligence_schema import (
    # Types
    AIMediaIntelligenceType, ContentWatermarkType, AIScanQueueType,
    CreatorAnalyticsType, ContentAnalyticsType, PlatformAnalyticsType,
    ContentScoreType, FeedRecommendationType, SuggestedCreatorType,
    
    # Input Types
    AIScanInput
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


def require_creator(user):
    """Check if user is creator"""
    if user.role != UserRoles.CREATOR:
        raise Exception("Creator access required")
    return True


@strawberry.type
class AIIntelligenceMutation:
    # AI Intelligence Mutations
    @strawberry.mutation
    def request_ai_scan(self, info: strawberry.types.Info, input: AIScanInput) -> AIScanQueueType:
        """Request AI scan for content"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.content.models import Content
        
        try:
            content = Content.objects.get(
                id=input.contentId,
                creator=user.creator_profile,
                tenant=user.tenant
            )
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        # Check if scan is already queued
        existing_scan = AIScanQueue.objects.filter(
            content=content,
            status__in=['queued', 'processing']
        ).first()
        
        if existing_scan:
            return AIScanQueueType.from_model(existing_scan)
        
        # Create scan job for each requested scan type
        scan_job = None
        for scan_type in input.scanTypes:
            job = AIScanQueue.objects.create(
                content=content,
                media=content.media.first(),  # Use first media file
                creator=user.creator_profile,
                tenant=user.tenant,
                job_type=scan_type,
                priority=input.priority
            )
            
            if scan_type == 'full_pipeline':
                scan_job = job
        
        return AIScanQueueType.from_model(scan_job) if scan_job else AIScanQueueType.from_model(job)

    @strawberry.mutation
    def process_ai_scan_queue(self, info: strawberry.types.Info, limit: int = 10) -> str:
        """Process AI scan queue (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        processed = 0
        failed = 0
        
        for _ in range(limit):
            job = AIScanQueue.get_next_job()
            if not job:
                break
            
            try:
                job.start_processing()
                
                # Process based on job type
                if job.job_type == 'fingerprint':
                    self._process_fingerprint(job)
                elif job.job_type == 'duplicate_check':
                    self._process_duplicate_check(job)
                elif job.job_type == 'watermark':
                    self._process_watermark(job)
                elif job.job_type == 'reverse_search':
                    self._process_reverse_search(job)
                elif job.job_type == 'price_benchmark':
                    self._process_price_benchmark(job)
                elif job.job_type == 'full_pipeline':
                    self._process_full_pipeline(job)
                
                job.complete_job()
                processed += 1
                
            except Exception as e:
                job.fail_job(str(e))
                failed += 1
        
        return f"Processed {processed} jobs, {failed} failed"

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
        
        # Calculate scores
        score.recency_score = score.calculate_recency_score()
        score.engagement_score = score.calculate_engagement_score()
        score.purchase_rate_score = score.calculate_purchase_rate_score()
        score.creator_tier_score = score.calculate_creator_tier_score()
        score.velocity_score = score.calculate_velocity_score()
        score.calculate_overall_score()
        score.update_trending_status()
        
        return ContentScoreType.from_model(score)

    @strawberry.mutation
    def regenerate_user_feed(self, info: strawberry.types.Info) -> List[FeedRecommendationType]:
        """Regenerate user's personalized feed"""
        user = require_auth(info)
        
        recommendations = FeedRecommendation.generate_user_feed(user, limit=50)
        
        return [FeedRecommendationType.from_model(rec) for rec in recommendations]

    @strawberry.mutation
    def regenerate_creator_suggestions(self, info: strawberry.types.Info) -> List[SuggestedCreatorType]:
        """Regenerate creator suggestions for user"""
        user = require_auth(info)
        
        suggestions = SuggestedCreator.generate_suggestions(user, limit=20)
        
        return [SuggestedCreatorType.from_model(suggestion) for suggestion in suggestions]

    @strawberry.mutation
    def record_recommendation_interaction(
        self,
        info: strawberry.types.Info,
        recommendationId: strawberry.ID,
        interactionType: str
    ) -> FeedRecommendationType:
        """Record user interaction with recommendation"""
        user = require_auth(info)
        
        try:
            recommendation = FeedRecommendation.objects.get(
                id=recommendationId,
                user=user
            )
        except FeedRecommendation.DoesNotExist:
            raise Exception("Recommendation not found")
        
        recommendation.record_interaction(interactionType)
        
        return FeedRecommendationType.from_model(recommendation)

    @strawberry.mutation
    def record_creator_suggestion_interaction(
        self,
        info: strawberry.types.Info,
        suggestionId: strawberry.ID,
        interactionType: str
    ) -> SuggestedCreatorType:
        """Record user interaction with creator suggestion"""
        user = require_auth(info)
        
        try:
            suggestion = SuggestedCreator.objects.get(
                id=suggestionId,
                user=user
            )
        except SuggestedCreator.DoesNotExist:
            raise Exception("Suggestion not found")
        
        suggestion.record_interaction(interactionType)
        
        return SuggestedCreatorType.from_model(suggestion)

    # Analytics Mutations
    @strawberry.mutation
    def generate_creator_analytics(self, info: strawberry.types.Info, date: Optional[timezone.datetime] = None) -> CreatorAnalyticsType:
        """Generate creator analytics for specific date (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        if not date:
            date = timezone.now().date()
        
        # This would typically run for all creators, but for demo we'll return current user's analytics
        if hasattr(user, 'creator_profile'):
            analytics = CreatorAnalytics.create_daily_snapshot(user.creator_profile, date)
            return CreatorAnalyticsType.from_model(analytics)
        
        raise Exception("No creator profile found")

    @strawberry.mutation
    def generate_platform_analytics(self, info: strawberry.types.Info, date: Optional[timezone.datetime] = None) -> PlatformAnalyticsType:
        """Generate platform analytics for specific date (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        if not date:
            date = timezone.now().date()
        
        analytics = PlatformAnalytics.create_daily_snapshot(date)
        return PlatformAnalyticsType.from_model(analytics)

    @strawberry.mutation
    def dismiss_creator_suggestion(self, info: strawberry.types.Info, suggestionId: strawberry.ID) -> SuggestedCreatorType:
        """Dismiss a creator suggestion"""
        user = require_auth(info)
        
        try:
            suggestion = SuggestedCreator.objects.get(
                id=suggestionId,
                user=user
            )
        except SuggestedCreator.DoesNotExist:
            raise Exception("Suggestion not found")
        
        suggestion.record_interaction('dismissed')
        
        return SuggestedCreatorType.from_model(suggestion)

    @strawberry.mutation
    def update_recommendation_feedback(
        self,
        info: strawberry.types.Info,
        recommendationId: strawberry.ID,
        feedback: int
    ) -> FeedRecommendationType:
        """Update feedback for recommendation"""
        user = require_auth(info)
        
        if feedback not in [-1, 0, 1]:
            raise Exception("Feedback must be -1, 0, or 1")
        
        try:
            recommendation = FeedRecommendation.objects.get(
                id=recommendationId,
                user=user
            )
        except FeedRecommendation.DoesNotExist:
            raise Exception("Recommendation not found")
        
        recommendation.user_feedback = feedback
        recommendation.save()
        
        return FeedRecommendationType.from_model(recommendation)

    # Helper methods for AI processing
    def _process_fingerprint(self, job):
        """Process fingerprint generation"""
        # Create or get AI intelligence record
        ai_intel, created = AIMediaIntelligence.objects.get_or_create(
            content=job.content,
            media=job.media,
            creator=job.creator,
            tenant=job.tenant
        )
        
        # Simulate fingerprint generation
        import hashlib
        import uuid
        
        # Generate fake hashes for demo
        ai_intel.sha256_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
        ai_intel.phash_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:64]
        ai_intel.dhash_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:64]
        ai_intel.combined_fingerprint = f"combined_{ai_intel.sha256_hash[:16]}_{ai_intel.phash_hash[:16]}"
        ai_intel.fingerprint_generated_at = timezone.now()
        ai_intel.save()

    def _process_duplicate_check(self, job):
        """Process duplicate detection"""
        ai_intel = AIMediaIntelligence.objects.get(
            content=job.content,
            media=job.media,
            creator=job.creator
        )
        
        # Simulate duplicate check (5% chance of finding duplicate)
        import random
        if random.random() < 0.05:
            # Find a random content to mark as duplicate
            from lipaidox.content.models import Content
            duplicate_content = Content.objects.exclude(id=job.content.id).order_by('?').first()
            if duplicate_content:
                ai_intel.mark_duplicate(
                    duplicate_content,
                    duplicate_content.media.first(),
                    0.85,  # 85% similarity
                    'flagged'
                )
        
        ai_intel.save()

    def _process_watermark(self, job):
        """Process watermark application"""
        watermark, created = ContentWatermark.objects.get_or_create(
            content=job.content,
            media=job.media,
            creator=job.creator,
            tenant=job.tenant
        )
        
        # Generate watermark data
        watermark.generate_invisible_payload()
        watermark.generate_visible_text()
        watermark.apply_watermark("https://storage.example.com/watermarked/" + str(job.media.id))
        
        watermark.save()

    def _process_reverse_search(self, job):
        """Process reverse image search"""
        ai_intel = AIMediaIntelligence.objects.get(
            content=job.content,
            media=job.media,
            creator=job.creator
        )
        
        # Simulate reverse search (10% chance of finding matches)
        import random
        if random.random() < 0.1:
            matches_count = random.randint(1, 5)
            results = {
                'matches': [
                    {'url': f'https://example.com/image{i}.jpg', 'similarity': random.uniform(0.7, 0.95)}
                    for i in range(matches_count)
                ]
            }
            ai_intel.update_reverse_scan('matches_found', matches_count, results)
        else:
            ai_intel.update_reverse_scan('clean')
        
        ai_intel.save()

    def _process_price_benchmark(self, job):
        """Process price benchmark analysis"""
        ai_intel = AIMediaIntelligence.objects.get(
            content=job.content,
            media=job.media,
            creator=job.creator
        )
        
        # Simulate price benchmark
        import random
        base_price = random.uniform(5.0, 50.0)
        ai_intel.set_price_benchmark(
            base_price * 0.8,  # min
            base_price * 1.2,  # max
            base_price        # avg
        )
        
        ai_intel.save()

    def _process_full_pipeline(self, job):
        """Process full AI pipeline"""
        # Run all steps
        self._process_fingerprint(job)
        self._process_duplicate_check(job)
        self._process_watermark(job)
        self._process_reverse_search(job)
        self._process_price_benchmark(job)
        
        # Mark overall scan as completed
        ai_intel = AIMediaIntelligence.objects.get(
            content=job.content,
            media=job.media,
            creator=job.creator
        )
        ai_intel.complete_scan()
