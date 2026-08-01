import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class CreatorAnalytics(TenantAwareModel):
    """
    Creator Analytics - Module 19
    Daily/weekly/monthly analytics snapshots for creators
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    period_date = models.DateField()
    period_type = models.CharField(
        max_length=20,
        default='daily',
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ]
    )

    # Audience Metrics
    follower_count = models.IntegerField(default=0)
    follower_gained = models.IntegerField(default=0)
    follower_lost = models.IntegerField(default=0)
    subscriber_count = models.IntegerField(default=0)
    subscriber_gained = models.IntegerField(default=0)
    subscriber_lost = models.IntegerField(default=0)

    # Content Metrics
    content_published = models.IntegerField(default=0)
    total_content_views = models.IntegerField(default=0)
    total_content_likes = models.IntegerField(default=0)
    total_content_comments = models.IntegerField(default=0)

    # Revenue Metrics
    revenue_from_subscriptions = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    revenue_from_ppv = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    revenue_from_tips = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    revenue_from_credits = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    revenue_from_live_streams = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    platform_fees_paid = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    net_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Live Streaming Metrics
    live_streams_count = models.IntegerField(default=0)
    live_stream_total_viewers = models.IntegerField(default=0)
    live_stream_peak_viewers = models.IntegerField(default=0)
    live_stream_duration_mins = models.IntegerField(default=0)

    # Engagement Metrics
    engagement_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    ppv_purchase_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    subscription_conversion_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)

    # Timestamps
    computed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'creator_analytics'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['creator'], name='idx_creator_analytics_creator'),
            models.Index(fields=['period_date'], name='idx_creator_analytics_date'),
            models.Index(fields=['period_type'], name='idx_creator_analytics_type'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['creator', 'period_date', 'period_type'],
                name='creator_analytics_unique'
            ),
            models.CheckConstraint(check=models.Q(follower_count__gte=0), name='creator_follower_count_check'),
            models.CheckConstraint(check=models.Q(subscriber_count__gte=0), name='subscriber_count_check'),
            models.CheckConstraint(check=models.Q(total_revenue__gte=0), name='revenue_check'),
            models.CheckConstraint(check=models.Q(net_revenue__gte=0), name='net_revenue_check'),
        ]

    def __str__(self):
        return f"Creator Analytics: {self.creator.user.username} - {self.period_date} ({self.period_type})"

    @classmethod
    def create_daily_snapshot(cls, creator, date):
        """Create daily analytics snapshot for a creator"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Get previous day's data for comparison
        prev_date = date - timedelta(days=1)
        prev_analytics = cls.objects.filter(
            creator=creator,
            period_date=prev_date,
            period_type='daily'
        ).first()

        # Calculate metrics (simplified - in real implementation would aggregate from various tables)
        follower_count = creator.followers.count()
        subscriber_count = creator.subscribers.filter(is_active=True).count()
        
        # Calculate changes
        follower_gained = max(0, follower_count - (prev_analytics.follower_count if prev_analytics else 0))
        follower_lost = max(0, (prev_analytics.follower_count if prev_analytics else 0) - follower_count)
        subscriber_gained = max(0, subscriber_count - (prev_analytics.subscriber_count if prev_analytics else 0))
        subscriber_lost = max(0, (prev_analytics.subscriber_count if prev_analytics else 0) - subscriber_count)

        # Get content metrics
        from lipaidox.content.models import Content, ContentMedia
        content_count = Content.objects.filter(
            creator=creator,
            created_at__date=date
        ).count()

        # Get revenue from wallet
        from lipaidox.wallet.models import WalletTransaction
        revenue_data = WalletTransaction.objects.filter(
            creator=creator,
            created_at__date=date
        ).aggregate(
            total=models.Sum('amount')
        )
        total_revenue = revenue_data['total'] or 0

        # Calculate engagement rate
        total_views = ContentMedia.objects.filter(
            content__creator=creator,
            created_at__date=date
        ).aggregate(total=models.Sum('view_count'))['total'] or 0
        
        total_likes = ContentMedia.objects.filter(
            content__creator=creator,
            created_at__date=date
        ).aggregate(total=models.Sum('like_count'))['total'] or 0
        
        engagement_rate = (total_likes / total_views) if total_views > 0 else 0

        return cls.objects.create(
            creator=creator,
            tenant=creator.tenant,
            period_date=date,
            period_type='daily',
            follower_count=follower_count,
            follower_gained=follower_gained,
            follower_lost=follower_lost,
            subscriber_count=subscriber_count,
            subscriber_gained=subscriber_gained,
            subscriber_lost=subscriber_lost,
            content_published=content_count,
            total_content_views=total_views,
            total_content_likes=total_likes,
            total_revenue=total_revenue,
            net_revenue=total_revenue * 0.85,  # Assuming 15% platform fee
            engagement_rate=engagement_rate,
        )

    def calculate_growth_rates(self, previous_period=None):
        """Calculate growth rates compared to previous period"""
        if not previous_period:
            return {}
        
        return {
            'follower_growth_rate': (
                ((self.follower_count - previous_period.follower_count) / previous_period.follower_count) * 100
                if previous_period.follower_count > 0 else 0
            ),
            'subscriber_growth_rate': (
                ((self.subscriber_count - previous_period.subscriber_count) / previous_period.subscriber_count) * 100
                if previous_period.subscriber_count > 0 else 0
            ),
            'revenue_growth_rate': (
                ((self.total_revenue - previous_period.total_revenue) / previous_period.total_revenue) * 100
                if previous_period.total_revenue > 0 else 0
            ),
        }
