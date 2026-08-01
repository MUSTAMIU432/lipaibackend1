import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class TrendingContent(RecommendationTenantAwareModel):
    """
    Trending Content - Module 23
    Platform-wide trending content tracking
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='trending_entries'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='trending_content'
    )
    trending_score = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
    rank_position = models.IntegerField()
    category = models.CharField(max_length=100, blank=True, null=True)
    audience_type = models.CharField(
        max_length=20,
        choices=[
            ('general', 'General'),
            ('adult', 'Adult'),
            ('teen', 'Teen'),
            ('mature', 'Mature'),
            ('family', 'Family')
        ],
        default='general'
    )
    trend_window_hours = models.IntegerField(default=24)
    computed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trending_content'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['rank_position'], name='idx_trending_content_rank'),
            models.Index(fields=['category'], name='idx_trending_content_category'),
            models.Index(fields=['audience_type'], name='idx_trending_content_audience'),
            models.Index(fields=['expires_at'], name='idx_trending_content_expires'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'trend_window_hours'],
                name='trending_content_unique'
            ),
            models.CheckConstraint(
                check=models.Q(rank_position__gte=1),
                name='rank_position_check'
            ),
            models.CheckConstraint(
                check=models.Q(trending_score__gte=0),
                name='recommendation_trending_score_check'
            ),
        ]

    def __str__(self):
        return f"Trending: {self.content.title} - Rank {self.rank_position}"

    def is_expired(self):
        """Check if trending entry has expired"""
        from django.utils import timezone
        return self.expires_at <= timezone.now()

    @classmethod
    def calculate_trending_score(cls, content, window_hours=24):
        """Calculate trending score for content"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.recommendation.models import UserInteraction
        
        # Get interactions within the time window
        cutoff_time = timezone.now() - timedelta(hours=window_hours)
        
        interactions = UserInteraction.objects.filter(
            content=content,
            interacted_at__gte=cutoff_time
        )
        
        # Weight different interactions differently
        weights = {
            'view': 1,
            'like': 5,
            'comment': 10,
            'share': 15,
            'purchase': 50,
            'tip': 30
        }
        
        score = 0
        for interaction_type, weight in weights.items():
            count = interactions.filter(interaction_type=interaction_type).count()
            score += count * weight
        
        # Apply time decay (more recent interactions weigh more)
        for interaction in interactions:
            hours_ago = (timezone.now() - interaction.interacted_at).total_seconds() / 3600
            time_weight = max(0.1, 1 - (hours_ago / window_hours))
            score += time_weight
        
        return score

    @classmethod
    def update_trending_content(cls, window_hours=24, limit=50):
        """Update trending content list"""
        from django.utils import timezone
        from datetime import timedelta
        from lipaidox.content.models import Content
        from lipaidox.recommendation.models import ContentScore
        
        # Clear existing trending entries for this window
        cls.objects.filter(trend_window_hours=window_hours).delete()
        
        # Get all content with recent activity
        cutoff_time = timezone.now() - timedelta(hours=window_hours)
        recent_content = Content.objects.filter(
            created_at__gte=cutoff_time
        ).select_related('creator')
        
        trending_scores = []
        
        for content in recent_content:
            score = cls.calculate_trending_score(content, window_hours)
            if score > 0:
                trending_scores.append((content, score))
        
        # Sort by score and create trending entries
        trending_scores.sort(key=lambda x: x[1], reverse=True)
        
        for rank, (content, score) in enumerate(trending_scores[:limit], start=1):
            cls.objects.create(
                content=content,
                creator=content.creator,
                tenant=content.tenant,
                trending_score=score,
                rank_position=rank,
                category=content.category or 'general',
                audience_type=content.audience_type or 'general',
                trend_window_hours=window_hours,
                expires_at=timezone.now() + timedelta(hours=window_hours)
            )

    @classmethod
    def get_trending_content(cls, category=None, audience_type=None, window_hours=24, limit=50):
        """Get trending content"""
        from django.utils import timezone
        
        queryset = cls.objects.filter(
            trend_window_hours=window_hours,
            expires_at__gt=timezone.now()
        ).select_related('content', 'creator')
        
        if category:
            queryset = queryset.filter(category=category)
        if audience_type:
            queryset = queryset.filter(audience_type=audience_type)
        
        return queryset.order_by('rank_position')[:limit]

    @classmethod
    def get_trending_categories(cls, limit=10):
        """Get trending categories"""
        from django.db.models import Count
        
        return cls.objects.filter(
            expires_at__gt=timezone.now()
        ).values('category').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

    @classmethod
    def get_creator_trending_rank(cls, creator, window_hours=24):
        """Get creator's best trending rank"""
        entry = cls.objects.filter(
            creator=creator,
            trend_window_hours=window_hours,
            expires_at__gt=timezone.now()
        ).order_by('rank_position').first()
        
        return entry.rank_position if entry else None

    @classmethod
    def cleanup_expired_entries(cls):
        """Remove expired trending entries"""
        from django.utils import timezone
        
        return cls.objects.filter(
            expires_at__lte=timezone.now()
        ).delete()[0]
