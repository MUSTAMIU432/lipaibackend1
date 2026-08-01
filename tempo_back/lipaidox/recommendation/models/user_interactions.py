import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class InteractionType(models.TextChoices):
    """Types of user interactions"""
    VIEW = 'view', 'View'
    LIKE = 'like', 'Like'
    UNLIKE = 'unlike', 'Unlike'
    COMMENT = 'comment', 'Comment'
    SHARE = 'share', 'Share'
    SAVE = 'save', 'Save'
    PURCHASE = 'purchase', 'Purchase'
    SUBSCRIBE = 'subscribe', 'Subscribe'
    UNSUBSCRIBE = 'unsubscribe', 'Unsubscribe'
    FOLLOW = 'follow', 'Follow'
    UNFOLLOW = 'unfollow', 'Unfollow'
    TIP = 'tip', 'Tip'
    SKIP = 'skip', 'Skip'
    REPORT = 'report', 'Report'


class UserInteraction(RecommendationTenantAwareModel):
    """
    User Interactions - Module 23
    Records every user engagement signal for recommendation algorithms
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='recommendation_interactions'
    )
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='interactions',
        null=True,
        blank=True
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='received_interactions',
        null=True,
        blank=True
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=InteractionType.choices
    )

    # Context
    watch_duration_s = models.IntegerField(null=True, blank=True)
    completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )
    source = models.CharField(
        max_length=50,
        choices=[
            ('feed', 'Feed'),
            ('explore', 'Explore'),
            ('search', 'Search'),
            ('recommendation', 'Recommendation'),
            ('profile', 'Profile'),
            ('trending', 'Trending'),
            ('direct_link', 'Direct Link')
        ],
        null=True,
        blank=True
    )
    device_type = models.CharField(max_length=50, blank=True, null=True)
    session_id = models.CharField(max_length=255, blank=True, null=True)

    # Timestamps
    interacted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_interactions'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['user'], name='idx_user_interactions_user'),
            models.Index(fields=['content'], name='idx_user_interactions_content'),
            models.Index(fields=['creator'], name='idx_user_interactions_creator'),
            models.Index(fields=['interaction_type'], name='idx_user_interactions_type'),
            models.Index(fields=['interacted_at'], name='idx_user_interactions_interact'),
            models.Index(fields=['source'], name='idx_user_interactions_source'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(watch_duration_s__isnull=True) | models.Q(watch_duration_s__gte=0),
                name='watch_duration_check'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(completion_rate__isnull=True) |
                    (models.Q(completion_rate__gte=0) & models.Q(completion_rate__lte=1))
                ),
                name='recommendation_completion_rate_check'
            ),
        ]

    def __str__(self):
        target = self.content.title if self.content else self.creator.user.username if self.creator else 'Unknown'
        return f"{self.user.username} {self.interaction_type} {target}"

    @classmethod
    def record_interaction(cls, user, interaction_type, content=None, creator=None, **kwargs):
        """Record a user interaction"""
        return cls.objects.create(
            user=user,
            tenant=user.tenant,
            content=content,
            creator=creator,
            interaction_type=interaction_type,
            **kwargs
        )

    @classmethod
    def record_view(cls, user, content, watch_duration=None, completion_rate=None, source=None):
        """Record a content view"""
        return cls.record_interaction(
            user=user,
            interaction_type=InteractionType.VIEW,
            content=content,
            creator=content.creator,
            watch_duration_s=watch_duration,
            completion_rate=completion_rate,
            source=source
        )

    @classmethod
    def record_like(cls, user, content):
        """Record a content like"""
        return cls.record_interaction(
            user=user,
            interaction_type=InteractionType.LIKE,
            content=content,
            creator=content.creator
        )

    @classmethod
    def record_purchase(cls, user, content, source=None):
        """Record a content purchase"""
        return cls.record_interaction(
            user=user,
            interaction_type=InteractionType.PURCHASE,
            content=content,
            creator=content.creator,
            source=source
        )

    @classmethod
    def record_follow(cls, user, creator, source=None):
        """Record a creator follow"""
        return cls.record_interaction(
            user=user,
            interaction_type=InteractionType.FOLLOW,
            creator=creator,
            source=source
        )

    @classmethod
    def record_subscribe(cls, user, creator, source=None):
        """Record a creator subscription"""
        return cls.record_interaction(
            user=user,
            interaction_type=InteractionType.SUBSCRIBE,
            creator=creator,
            source=source
        )

    @classmethod
    def get_user_interactions(cls, user, interaction_type=None, days=30):
        """Get user's interactions for the last N days"""
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = cls.objects.filter(
            user=user,
            interacted_at__gte=timezone.now() - timedelta(days=days)
        )
        
        if interaction_type:
            queryset = queryset.filter(interaction_type=interaction_type)
        
        return queryset

    @classmethod
    def get_content_interactions(cls, content, interaction_type=None, days=30):
        """Get content interactions for the last N days"""
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = cls.objects.filter(
            content=content,
            interacted_at__gte=timezone.now() - timedelta(days=days)
        )
        
        if interaction_type:
            queryset = queryset.filter(interaction_type=interaction_type)
        
        return queryset

    @classmethod
    def get_creator_interactions(cls, creator, interaction_type=None, days=30):
        """Get creator interactions for the last N days"""
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = cls.objects.filter(
            creator=creator,
            interacted_at__gte=timezone.now() - timedelta(days=days)
        )
        
        if interaction_type:
            queryset = queryset.filter(interaction_type=interaction_type)
        
        return queryset
