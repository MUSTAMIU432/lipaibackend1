import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ContentAnalytics(TenantAwareModel):
    """
    Content Analytics - Module 19
    Performance analytics for individual content pieces
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='content_analytics'
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

    # View Metrics
    view_count = models.IntegerField(default=0)
    unique_view_count = models.IntegerField(default=0)
    average_watch_duration_s = models.IntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # Engagement Metrics
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)
    save_count = models.IntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)

    # Revenue Metrics
    ppv_purchases = models.IntegerField(default=0)
    ppv_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    tip_count = models.IntegerField(default=0)
    tip_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Audience Metrics
    subscriber_views = models.IntegerField(default=0)
    non_subscriber_views = models.IntegerField(default=0)
    new_subscribers_from_content = models.IntegerField(default=0)

    # Timestamps
    computed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'content_analytics'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['content'], name='idx_content_analytics_content'),
            models.Index(fields=['creator'], name='idx_content_analytics_creator'),
            models.Index(fields=['period_date'], name='idx_content_analytics_date'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['content', 'period_date', 'period_type'],
                name='content_analytics_unique'
            ),
            models.CheckConstraint(check=models.Q(view_count__gte=0), name='view_count_check'),
            models.CheckConstraint(
                check=models.Q(engagement_rate__range=(0, 1)),
                name='engagement_rate_check'
            ),
            models.CheckConstraint(
                check=models.Q(completion_rate__range=(0, 1)),
                name='completion_rate_check'
            ),
        ]

    def __str__(self):
        return f"Content Analytics: {self.content.title} - {self.period_date} ({self.period_type})"

    @classmethod
    def create_daily_snapshot(cls, content, date):
        """Create daily analytics snapshot for content"""
        from lipaidox.content.models import ContentMedia
        from lipaidox.ppv.models import PPVPurchase
        from lipaidox.tips.models import Tip
        from lipaidox.subscriptions.models import Subscription
        
        # Get media metrics
        media_queryset = ContentMedia.objects.filter(content=content)
        
        # Aggregate view metrics
        view_data = media_queryset.aggregate(
            total_views=models.Sum('view_count'),
            total_likes=models.Sum('like_count'),
            total_comments=models.Sum('comment_count'),
            avg_duration=models.Avg('average_watch_duration')
        )
        
        view_count = view_data['total_views'] or 0
        like_count = view_data['total_likes'] or 0
        comment_count = view_data['total_comments'] or 0
        avg_duration = int(view_data['avg_duration'] or 0)
        
        # Calculate engagement rate
        engagement_rate = (like_count + comment_count) / view_count if view_count > 0 else 0
        
        # Get PPV revenue
        ppv_data = PPVPurchase.objects.filter(
            content=content,
            created_at__date=date,
            status='completed'
        ).aggregate(
            purchases=models.Count('id'),
            revenue=models.Sum('net_amount')
        )
        
        ppv_purchases = ppv_data['purchases'] or 0
        ppv_revenue = ppv_data['revenue'] or 0
        
        # Get tip revenue
        tip_data = Tip.objects.filter(
            content=content,
            created_at__date=date
        ).aggregate(
            count=models.Count('id'),
            revenue=models.Sum('net_amount')
        )
        
        tip_count = tip_data['count'] or 0
        tip_revenue = tip_data['revenue'] or 0
        
        # Calculate subscriber vs non-subscriber views
        subscriber_views = media_queryset.filter(
            viewers__user__subscriptions__creator=content.creator,
            viewers__user__subscriptions__is_active=True
        ).distinct().count()
        
        non_subscriber_views = view_count - subscriber_views
        
        # Get new subscribers from this content
        new_subs = Subscription.objects.filter(
            creator=content.creator,
            created_at__date=date,
            reference_content=content
        ).count()
        
        return cls.objects.create(
            content=content,
            creator=content.creator,
            tenant=content.tenant,
            period_date=date,
            period_type='daily',
            view_count=view_count,
            unique_view_count=view_count,  # Simplified
            average_watch_duration_s=avg_duration,
            completion_rate=0.85,  # Simplified
            like_count=like_count,
            comment_count=comment_count,
            share_count=0,  # Would need separate tracking
            save_count=0,   # Would need separate tracking
            engagement_rate=engagement_rate,
            ppv_purchases=ppv_purchases,
            ppv_revenue=ppv_revenue,
            tip_count=tip_count,
            tip_revenue=tip_revenue,
            total_revenue=ppv_revenue + tip_revenue,
            subscriber_views=subscriber_views,
            non_subscriber_views=non_subscriber_views,
            new_subscribers_from_content=new_subs,
        )

    def calculate_performance_score(self):
        """Calculate overall performance score (0-100)"""
        score = 0
        
        # View performance (30% weight)
        if self.view_count > 1000:
            score += 30
        elif self.view_count > 500:
            score += 20
        elif self.view_count > 100:
            score += 10
        
        # Engagement rate (25% weight)
        if self.engagement_rate > 0.1:  # 10%
            score += 25
        elif self.engagement_rate > 0.05:  # 5%
            score += 15
        elif self.engagement_rate > 0.02:  # 2%
            score += 8
        
        # Revenue performance (25% weight)
        if self.total_revenue > 100:
            score += 25
        elif self.total_revenue > 50:
            score += 15
        elif self.total_revenue > 10:
            score += 8
        
        # Completion rate (20% weight)
        if self.completion_rate > 0.8:  # 80%
            score += 20
        elif self.completion_rate > 0.6:  # 60%
            score += 12
        elif self.completion_rate > 0.4:  # 40%
            score += 6
        
        return min(score, 100)

    def get_insights(self):
        """Get insights about content performance"""
        insights = []
        
        if self.engagement_rate > 0.1:
            insights.append("High engagement rate - content resonates well with audience")
        elif self.engagement_rate < 0.02:
            insights.append("Low engagement - consider improving content quality or promotion")
        
        if self.ppv_purchases > 50:
            insights.append("Strong PPV performance - content has high perceived value")
        
        if self.new_subscribers_from_content > 10:
            insights.append("Effective subscriber acquisition - content attracts new fans")
        
        if self.completion_rate > 0.8:
            insights.append("High completion rate - content maintains viewer interest")
        
        return insights
