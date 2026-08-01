import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PlatformAnalytics(TenantAwareModel):
    """
    Platform Analytics - Module 19
    Platform-wide analytics for admin dashboard
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    # User Metrics
    total_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    total_creators = models.IntegerField(default=0)
    new_creators = models.IntegerField(default=0)
    active_creators = models.IntegerField(default=0)
    total_fans = models.IntegerField(default=0)
    new_fans = models.IntegerField(default=0)

    # Content Metrics
    total_content_published = models.IntegerField(default=0)
    total_content_views = models.IntegerField(default=0)
    total_live_streams = models.IntegerField(default=0)

    # Revenue Metrics
    gross_revenue = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    platform_fees_collected = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_payouts = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_refunds = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Subscription Metrics
    new_subscriptions = models.IntegerField(default=0)
    cancelled_subscriptions = models.IntegerField(default=0)
    active_subscriptions = models.IntegerField(default=0)

    # Credits Metrics
    creator_credits_sold = models.IntegerField(default=0)
    fan_credits_sold = models.IntegerField(default=0)
    fan_credits_gifted = models.IntegerField(default=0)

    # Timestamps
    computed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_analytics'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['period_date'], name='idx_platform_analytics_date'),
            models.Index(fields=['period_type'], name='idx_platform_analytics_type'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['period_date', 'period_type'],
                name='platform_analytics_unique'
            ),
        ]

    def __str__(self):
        return f"Platform Analytics: {self.period_date} ({self.period_type})"

    @classmethod
    def create_daily_snapshot(cls, date):
        """Create daily platform analytics snapshot"""
        from django.contrib.auth import get_user_model
        from lipaidox.creator_profile.models import CreatorProfile
        from lipaidox.content.models import Content, ContentMedia
        from lipaidox.wallet.models import Transaction, PayoutTransaction
        from lipaidox.subscriptions.models import Subscription
        from lipaidox.credits.models import FanCreditPurchase, FanCreditGiftSent
        from lipaidox.live_streaming.models import LiveStream
        
        User = get_user_model()
        
        # User metrics
        total_users = User.objects.filter(is_active=True).count()
        new_users = User.objects.filter(
            date_joined__date=date,
            is_active=True
        ).count()
        
        total_creators = CreatorProfile.objects.filter(
            user__is_active=True
        ).count()
        new_creators = CreatorProfile.objects.filter(
            user__date_joined__date=date,
            user__is_active=True
        ).count()
        
        active_creators = CreatorProfile.objects.filter(
            user__is_active=True,
            content__created_at__date=date
        ).distinct().count()
        
        total_fans = User.objects.filter(
            is_active=True
        ).exclude(creator_profile__isnull=False).count()
        new_fans = User.objects.filter(
            date_joined__date=date,
            is_active=True
        ).exclude(creator_profile__isnull=False).count()
        
        # Content metrics
        total_content_published = Content.objects.filter(
            created_at__date=date
        ).count()
        
        total_content_views = ContentMedia.objects.filter(
            created_at__date=date
        ).aggregate(total=models.Sum('view_count'))['total'] or 0
        
        total_live_streams = LiveStream.objects.filter(
            created_at__date=date
        ).count()
        
        # Revenue metrics
        revenue_data = Transaction.objects.filter(
            created_at__date=date
        ).aggregate(
            gross=models.Sum('gross_amount'),
            fees=models.Sum('platform_fee')
        )
        
        gross_revenue = revenue_data['gross'] or 0
        platform_fees_collected = revenue_data['fees'] or 0
        
        total_payouts = PayoutTransaction.objects.filter(
            created_at__date=date,
            status='completed'
        ).aggregate(total=models.Sum('net_payout_amount'))['total'] or 0
        
        total_refunds = Transaction.objects.filter(
            created_at__date=date,
            refund_amount__isnull=False
        ).aggregate(total=models.Sum('refund_amount'))['total'] or 0
        
        # Subscription metrics
        new_subscriptions = Subscription.objects.filter(
            created_at__date=date,
            is_active=True
        ).count()
        
        cancelled_subscriptions = Subscription.objects.filter(
            cancelled_at__date=date
        ).count()
        
        active_subscriptions = Subscription.objects.filter(
            is_active=True
        ).count()
        
        # Credits metrics
        creator_credits_sold = FanCreditPurchase.objects.filter(
            created_at__date=date,
            purchase_type='creator_credits'
        ).aggregate(total=models.Sum('credit_amount'))['total'] or 0
        
        fan_credits_sold = FanCreditPurchase.objects.filter(
            created_at__date=date,
            purchase_type='fan_credits'
        ).aggregate(total=models.Sum('credit_amount'))['total'] or 0
        
        fan_credits_gifted = FanCreditGiftSent.objects.filter(
            created_at__date=date
        ).aggregate(total=models.Sum('credit_amount'))['total'] or 0
        
        return cls.objects.create(
            period_date=date,
            period_type='daily',
            total_users=total_users,
            new_users=new_users,
            active_users=new_users,  # Simplified - would need actual activity tracking
            total_creators=total_creators,
            new_creators=new_creators,
            active_creators=active_creators,
            total_fans=total_fans,
            new_fans=new_fans,
            total_content_published=total_content_published,
            total_content_views=total_content_views,
            total_live_streams=total_live_streams,
            gross_revenue=gross_revenue,
            platform_fees_collected=platform_fees_collected,
            total_payouts=total_payouts,
            total_refunds=total_refunds,
            new_subscriptions=new_subscriptions,
            cancelled_subscriptions=cancelled_subscriptions,
            active_subscriptions=active_subscriptions,
            creator_credits_sold=creator_credits_sold,
            fan_credits_sold=fan_credits_sold,
            fan_credits_gifted=fan_credits_gifted,
        )

    def calculate_growth_rates(self, previous_period=None):
        """Calculate growth rates compared to previous period"""
        if not previous_period:
            return {}
        
        return {
            'user_growth_rate': (
                ((self.total_users - previous_period.total_users) / previous_period.total_users) * 100
                if previous_period.total_users > 0 else 0
            ),
            'creator_growth_rate': (
                ((self.total_creators - previous_period.total_creators) / previous_period.total_creators) * 100
                if previous_period.total_creators > 0 else 0
            ),
            'revenue_growth_rate': (
                ((self.gross_revenue - previous_period.gross_revenue) / previous_period.gross_revenue) * 100
                if previous_period.gross_revenue > 0 else 0
            ),
            'content_growth_rate': (
                ((self.total_content_published - previous_period.total_content_published) / previous_period.total_content_published) * 100
                if previous_period.total_content_published > 0 else 0
            ),
        }

    def get_key_metrics(self):
        """Get key performance indicators"""
        return {
            'avg_revenue_per_user': (
                self.gross_revenue / self.active_users
                if self.active_users > 0 else 0
            ),
            'avg_revenue_per_creator': (
                self.gross_revenue / self.active_creators
                if self.active_creators > 0 else 0
            ),
            'creator_to_user_ratio': (
                (self.total_creators / self.total_users) * 100
                if self.total_users > 0 else 0
            ),
            'subscription_conversion_rate': (
                (self.active_subscriptions / self.total_fans) * 100
                if self.total_fans > 0 else 0
            ),
            'platform_fee_percentage': (
                (self.platform_fees_collected / self.gross_revenue) * 100
                if self.gross_revenue > 0 else 0
            ),
        }
