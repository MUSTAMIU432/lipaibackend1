import uuid
from django.db import models
from .base import RecommendationTenantAwareModel


class UserInterestProfile(RecommendationTenantAwareModel):
    """
    User Interest Profiles - Module 23
    Computed interest profile per user for recommendations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='interest_profile'
    )

    # Category Weights - computed from interaction history
    category_weights = models.JSONField(default=dict)

    # Behaviour Signals
    preferred_content_formats = models.TextField(default='[]')  # JSON array
    preferred_access_types = models.TextField(default='[]')  # JSON array
    avg_watch_completion_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.00)
    purchase_propensity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0.00)
    tip_propensity_score = models.DecimalField(max_digits=5, decimal_places=4, default=0.00)

    # Activity
    total_interactions = models.IntegerField(default=0)
    last_active_at = models.DateTimeField(null=True, blank=True)
    profile_confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0.00)

    # Timestamps
    last_computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_interest_profiles'
        app_label = 'lipaidox_recommendation'
        indexes = [
            models.Index(fields=['user'], name='idx_user_interest_profiles_usr'),
            models.Index(fields=['last_active_at'], name='idx_user_interest_profiles_lst'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='user_interest_profiles_unique'
            ),
            models.CheckConstraint(
                check=models.Q(purchase_propensity_score__range=(0, 1)),
                name='purchase_propensity_check'
            ),
            models.CheckConstraint(
                check=models.Q(profile_confidence_score__range=(0, 1)),
                name='confidence_score_check'
            ),
        ]

    def __str__(self):
        return f"Interest Profile: {self.user.username}"

    def get_category_weights(self):
        """Get category weights as dictionary"""
        import json
        return json.loads(self.category_weights) if self.category_weights else {}

    def set_category_weights(self, weights_dict):
        """Set category weights from dictionary"""
        import json
        self.category_weights = json.dumps(weights_dict)
        self.save()

    def get_preferred_content_formats(self):
        """Get preferred content formats as list"""
        import json
        return json.loads(self.preferred_content_formats) if self.preferred_content_formats else []

    def set_preferred_content_formats(self, formats_list):
        """Set preferred content formats from list"""
        import json
        self.preferred_content_formats = json.dumps(formats_list)
        self.save()

    def get_preferred_access_types(self):
        """Get preferred access types as list"""
        import json
        return json.loads(self.preferred_access_types) if self.preferred_access_types else []

    def set_preferred_access_types(self, types_list):
        """Set preferred access types from list"""
        import json
        self.preferred_access_types = json.dumps(types_list)
        self.save()

    def update_category_weights(self):
        """Update category weights based on interaction history"""
        from lipaidox.recommendation.models import UserInteraction
        from django.db.models import Count, Q
        import json
        
        # Get user's content interactions
        interactions = UserInteraction.objects.filter(
            user=self.user,
            content__isnull=False,
            interaction_type__in=['view', 'like', 'comment', 'share', 'purchase']
        ).values('content__category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Calculate weights
        total_interactions = sum(item['count'] for item in interactions)
        
        if total_interactions == 0:
            self.set_category_weights({})
            return
        
        category_weights = {}
        for interaction in interactions:
            category = interaction['content__category']
            if category:
                weight = interaction['count'] / total_interactions
                category_weights[category] = round(weight, 3)
        
        self.set_category_weights(category_weights)

    def update_content_preferences(self):
        """Update content format and access type preferences"""
        from lipaidox.recommendation.models import UserInteraction
        from lipaidox.content.models import Content
        import json
        
        # Get preferred content formats (video, image, audio, etc.)
        content_formats = Content.objects.filter(
            interactions__user=self.user
        ).values_list('content_type', flat=True).annotate(
            count=models.Count('id')
        ).order_by('-count').values_list('content_type', flat=True)[:5]
        
        self.set_preferred_content_formats(list(content_formats))
        
        # Get preferred access types (ppv, subscription, free, etc.)
        access_types = UserInteraction.objects.filter(
            user=self.user,
            interaction_type='purchase'
        ).values('content__access_type').annotate(
            count=models.Count('id')
        ).order_by('-count').values_list('content__access_type', flat=True)[:5]
        
        self.set_preferred_access_types(list(access_types))

    def update_propensity_scores(self):
        """Update purchase and tip propensity scores"""
        from lipaidox.recommendation.models import UserInteraction
        from django.utils import timezone
        from datetime import timedelta
        
        # Get interactions from last 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        
        interactions = UserInteraction.objects.filter(
            user=self.user,
            interacted_at__gte=cutoff_date
        )
        
        total_interactions = interactions.count()
        if total_interactions == 0:
            self.purchase_propensity_score = 0
            self.tip_propensity_score = 0
            self.save()
            return
        
        # Purchase propensity
        purchase_interactions = interactions.filter(interaction_type='purchase').count()
        self.purchase_propensity_score = round(purchase_interactions / total_interactions, 4)
        
        # Tip propensity
        tip_interactions = interactions.filter(interaction_type='tip').count()
        self.tip_propensity_score = round(tip_interactions / total_interactions, 4)
        
        self.save()

    def update_completion_rate(self):
        """Update average watch completion rate"""
        from lipaidox.recommendation.models import UserInteraction
        from django.db.models import Avg
        
        avg_rate = UserInteraction.objects.filter(
            user=self.user,
            completion_rate__isnull=False
        ).aggregate(avg_rate=Avg('completion_rate'))['avg_rate']
        
        self.avg_watch_completion_rate = round(avg_rate or 0, 4)
        self.save()

    def update_activity_metrics(self):
        """Update activity metrics"""
        from lipaidox.recommendation.models import UserInteraction
        from django.utils import timezone
        
        # Total interactions
        self.total_interactions = UserInteraction.objects.filter(user=self.user).count()
        
        # Last active at
        last_interaction = UserInteraction.objects.filter(
            user=self.user
        ).order_by('-interacted_at').first()
        
        self.last_active_at = last_interaction.interacted_at if last_interaction else None
        
        # Profile confidence score based on interaction count
        if self.total_interactions >= 100:
            self.profile_confidence_score = 1.0
        elif self.total_interactions >= 50:
            self.profile_confidence_score = 0.8
        elif self.total_interactions >= 20:
            self.profile_confidence_score = 0.6
        elif self.total_interactions >= 10:
            self.profile_confidence_score = 0.4
        else:
            self.profile_confidence_score = 0.2
        
        self.save()

    def compute_profile(self):
        """Compute complete user interest profile"""
        self.update_category_weights()
        self.update_content_preferences()
        self.update_propensity_scores()
        self.update_completion_rate()
        self.update_activity_metrics()

    @classmethod
    def get_or_create_profile(cls, user):
        """Get or create user interest profile"""
        profile, created = cls.objects.get_or_create(
            user=user,
            tenant=user.tenant
        )
        
        if created or not profile.last_computed_at:
            profile.compute_profile()
        
        return profile

    @classmethod
    def compute_all_profiles(cls):
        """Compute profiles for all users"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        users = User.objects.filter(is_active=True)
        
        for user in users:
            cls.get_or_create_profile(user)

    def get_top_categories(self, limit=5):
        """Get user's top preferred categories"""
        category_weights = self.get_category_weights()
        
        # Sort by weight and return top N
        sorted_categories = sorted(
            category_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_categories[:limit]

    def is_interested_in_category(self, category, threshold=0.1):
        """Check if user is interested in a category"""
        category_weights = self.get_category_weights()
        return category_weights.get(category, 0) >= threshold

    def get_profile_summary(self):
        """Get summary of user's interest profile"""
        return {
            'top_categories': self.get_top_categories(3),
            'preferred_formats': self.get_preferred_content_formats(),
            'purchase_propensity': float(self.purchase_propensity_score),
            'tip_propensity': float(self.tip_propensity_score),
            'avg_completion_rate': float(self.avg_watch_completion_rate),
            'profile_confidence': float(self.profile_confidence_score),
            'total_interactions': self.total_interactions,
            'last_active': self.last_active_at.isoformat() if self.last_active_at else None
        }
