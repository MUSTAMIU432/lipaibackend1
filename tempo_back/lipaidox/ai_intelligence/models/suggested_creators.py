import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class SuggestedCreator(TenantAwareModel):
    """
    Suggested Creators - Module 23
    Creator recommendations for fans to discover
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='suggested_creators'
    )
    suggested_creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='suggested_to_users'
    )

    # Recommendation Scores
    category_match_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    popularity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    compatibility_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    growth_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    
    # Overall Recommendation Score
    suggestion_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # 0-1
    suggestion_rank = models.IntegerField(default=0)  # Rank in user's suggestions
    
    # Recommendation Context
    suggestion_reasons = models.JSONField(default=list, blank=True)
    matching_categories = models.JSONField(default=list, blank=True)
    
    # User Interaction Tracking
    shown_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    followed_at = models.DateTimeField(null=True, blank=True)
    subscribed_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    # Feedback
    user_feedback = models.IntegerField(default=0)  # -1 (not interested) to 1 (interested)
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'suggested_creators'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['user'], name='idx_suggested_creators_user'),
            models.Index(fields=['suggested_creator'], name='idx_suggested_creators_creator'),
            models.Index(fields=['-suggestion_score'], name='idx_suggested_creators_score'),
            models.Index(fields=['suggestion_rank'], name='idx_suggested_creators_rank'),
            models.Index(fields=['generated_at'], name='idx_suggested_creators_gen'),
            models.Index(fields=['expires_at'], name='idx_suggested_creators_expires'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'suggested_creator'],
                name='suggested_creators_unique'
            ),
            models.CheckConstraint(
                check=models.Q(suggestion_score__range=(0, 1)),
                name='suggestion_score_check'
            ),
            models.CheckConstraint(
                check=models.Q(user_feedback__range=(-1, 1)),
                name='creator_feedback_check'
            ),
        ]

    def __str__(self):
        return f"Suggested Creator: {self.user.username} -> {self.suggested_creator.user.username}"

    def calculate_category_match_score(self):
        """Calculate category match based on user's interests"""
        from lipaidox.content.models import Content
        from lipaidox.subscriptions.models import Subscription
        
        # Get user's subscribed creators' categories
        user_categories = Subscription.objects.filter(
            user=self.user,
            is_active=True
        ).values_list('creator__content__category', flat=True).distinct()
        
        # Get suggested creator's content categories
        creator_categories = Content.objects.filter(
            creator=self.suggested_creator
        ).values_list('category', flat=True).distinct()
        
        if not creator_categories:
            return 0
        
        # Calculate overlap
        matching_categories = set(user_categories) & set(creator_categories)
        
        if not user_categories:
            # New user - suggest popular categories
            popular_categories = ['general', 'lifestyle', 'entertainment']
            overlap = set(creator_categories) & set(popular_categories)
            score = len(overlap) / len(creator_categories)
        else:
            score = len(matching_categories) / len(creator_categories)
        
        self.matching_categories = list(matching_categories)
        self.save()
        
        return min(score, 1.0)

    def calculate_popularity_score(self):
        """Calculate popularity score based on creator's metrics"""
        creator = self.suggested_creator
        
        # Normalize popularity metrics
        follower_score = min(creator.followers.count() / 10000, 1.0)  # 10k followers = 1.0
        subscriber_score = min(creator.subscribers.count() / 1000, 1.0)  # 1k subscribers = 1.0
        
        # Content quality score
        from lipaidox.content.models import Content
        content_count = Content.objects.filter(creator=creator).count()
        content_score = min(content_count / 100, 1.0)  # 100 posts = 1.0
        
        # Verification bonus
        verification_bonus = 0.2 if creator.is_verified else 0
        
        popularity = (
            follower_score * 0.4 +
            subscriber_score * 0.4 +
            content_score * 0.2 +
            verification_bonus
        )
        
        return min(popularity, 1.0)

    def calculate_compatibility_score(self):
        """Calculate compatibility based on user behavior patterns"""
        from lipaidox.subscriptions.models import Subscription
        from lipaidox.content.models import Content
        
        # Check if user follows similar creators
        user_subscriptions = Subscription.objects.filter(
            user=self.user,
            is_active=True
        ).select_related('creator')
        
        if not user_subscriptions:
            return 0.5  # Neutral for new users
        
        # Calculate similarity with user's subscribed creators
        similarities = []
        
        for sub in user_subscriptions:
            # Compare tier
            tier_similarity = 1.0 - abs(
                self.suggested_creator.tier_score - sub.creator.tier_score
            )
            
            # Compare content frequency
            suggested_content_count = Content.objects.filter(
                creator=self.suggested_creator
            ).count()
            
            sub_content_count = Content.objects.filter(
                creator=sub.creator
            ).count()
            
            if suggested_content_count + sub_content_count > 0:
                content_similarity = min(
                    suggested_content_count, sub_content_count
                ) / max(suggested_content_count, sub_content_count)
            else:
                content_similarity = 0
            
            similarities.append((tier_similarity + content_similarity) / 2)
        
        return sum(similarities) / len(similarities) if similarities else 0.5

    def calculate_growth_score(self):
        """Calculate growth score based on creator's recent growth"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.subscriptions.models import Subscription
        
        # Get subscriber growth in last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        recent_subs = Subscription.objects.filter(
            creator=self.suggested_creator,
            created_at__gte=thirty_days_ago,
            is_active=True
        ).count()
        
        total_subs = self.suggested_creator.subscribers.filter(is_active=True).count()
        
        if total_subs == 0:
            return 0
        
        growth_rate = recent_subs / total_subs
        
        # Normalize to 0-1 scale (20% monthly growth = 1.0)
        return min(growth_rate / 0.2, 1.0)

    def calculate_suggestion_score(self):
        """Calculate overall suggestion score"""
        # Weights for different factors
        weights = {
            'category_match': 0.35,
            'popularity': 0.25,
            'compatibility': 0.25,
            'growth': 0.15,
        }
        
        overall = (
            self.category_match_score * weights['category_match'] +
            self.popularity_score * weights['popularity'] +
            self.compatibility_score * weights['compatibility'] +
            self.growth_score * weights['growth']
        )
        
        self.suggestion_score = min(overall, 1.0)
        self.save()
        
        return self.suggestion_score

    def generate_suggestion_reasons(self):
        """Generate human-readable suggestion reasons"""
        reasons = []
        
        if self.category_match_score > 0.7:
            reasons.append(f"Similar to creators you follow in {', '.join(self.matching_categories)}")
        
        if self.popularity_score > 0.8:
            reasons.append("Popular creator with growing community")
        
        if self.growth_score > 0.6:
            reasons.append("Fast-growing creator worth watching early")
        
        if self.suggested_creator.is_verified:
            reasons.append("Verified creator")
        
        if self.compatibility_score > 0.7:
            reasons.append("Matches your content preferences")
        
        self.suggestion_reasons = reasons
        self.save()
        
        return reasons

    def record_interaction(self, interaction_type):
        """Record user interaction with suggested creator"""
        from django.utils import timezone
        
        now = timezone.now()
        
        if interaction_type == 'shown':
            self.shown_at = now
        elif interaction_type == 'viewed':
            self.viewed_at = now
        elif interaction_type == 'followed':
            self.followed_at = now
            self.user_feedback = 1
        elif interaction_type == 'subscribed':
            self.subscribed_at = now
            self.user_feedback = 1
        elif interaction_type == 'dismissed':
            self.dismissed_at = now
            self.user_feedback = -1
        
        self.save()

    def is_expired(self):
        """Check if suggestion has expired"""
        from django.utils import timezone
        return self.expires_at and self.expires_at <= timezone.now()

    @classmethod
    def generate_suggestions(cls, user, limit=20):
        """Generate creator suggestions for user"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.subscriptions.models import Subscription
        
        # Get creators user already follows
        subscribed_creators = Subscription.objects.filter(
            user=user,
            is_active=True
        ).values_list('creator_id', flat=True)
        
        # Get potential creators to suggest
        from lipaidox.creator_profile.models import CreatorProfile
        
        potential_creators = CreatorProfile.objects.exclude(
            id__in=subscribed_creators
        ).exclude(
            user=user
        ).filter(
            user__is_active=True
        ).select_related('user').distinct()
        
        suggestions = []
        
        for creator in potential_creators:
            # Check if suggestion already exists
            existing = cls.objects.filter(
                user=user,
                suggested_creator=creator
            ).first()
            
            if existing and not existing.is_expired():
                suggestions.append(existing)
                continue
            
            # Create new suggestion
            suggestion = cls.objects.create(
                user=user,
                suggested_creator=creator,
                tenant=user.tenant,
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            # Calculate scores
            suggestion.category_match_score = suggestion.calculate_category_match_score()
            suggestion.popularity_score = suggestion.calculate_popularity_score()
            suggestion.compatibility_score = suggestion.calculate_compatibility_score()
            suggestion.growth_score = suggestion.calculate_growth_score()
            suggestion.calculate_suggestion_score()
            suggestion.generate_suggestion_reasons()
            
            # Only include if score is above threshold
            if suggestion.suggestion_score >= 0.3:
                suggestions.append(suggestion)
        
        # Sort by suggestion score and limit
        suggestions.sort(key=lambda x: x.suggestion_score, reverse=True)
        
        # Update suggestion ranks
        for i, suggestion in enumerate(suggestions[:limit]):
            suggestion.suggestion_rank = i + 1
            suggestion.save()
        
        return suggestions[:limit]

    @classmethod
    def get_user_suggestions(cls, user, limit=20):
        """Get existing user suggestions or generate new ones"""
        from django.utils import timezone
        
        # Check for existing fresh suggestions
        existing_suggestions = cls.objects.filter(
            user=user,
            expires_at__gt=timezone.now()
        ).select_related('suggested_creator__user').order_by(
            '-suggestion_score'
        )[:limit]
        
        if len(existing_suggestions) >= limit // 2:
            return existing_suggestions
        
        # Generate new suggestions
        return cls.generate_suggestions(user, limit)
