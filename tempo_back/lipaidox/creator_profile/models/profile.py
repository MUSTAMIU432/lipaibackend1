import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from django.conf import settings
from lipaidox.creator_plans.constants import CreatorPlanTier

class ProfileStatus(models.TextChoices):
    INCOMPLETE = 'incomplete', 'Incomplete'
    COMPLETE = 'complete', 'Complete'
    SUSPENDED = 'suspended', 'Suspended'
    DEACTIVATED = 'deactivated', 'Deactivated'

class CreatorTier(models.TextChoices):
    BRONZE = 'bronze', 'Bronze'
    SILVER = 'silver', 'Silver'
    GOLD = 'gold', 'Gold'
    PLATINUM = 'platinum', 'Platinum'

class CreatorProfile(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField("lipaidox_auth.User", on_delete=models.CASCADE, related_name="profile")
    
    # Public identity
    username = models.CharField(max_length=50, unique=True)
    bio = models.TextField(max_length=1000, null=True, blank=True)
    profile_photo_url = models.URLField(max_length=500, null=True, blank=True)
    cover_photo_url = models.URLField(max_length=500, null=True, blank=True)
    website_url = models.URLField(max_length=500, null=True, blank=True)

    # Location & Language
    nationality = models.CharField(max_length=100, null=True, blank=True)
    country_of_residence = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    preferred_language = models.CharField(max_length=50, null=True, blank=True)
    timezone = models.CharField(max_length=100, null=True, blank=True)

    # Gender
    gender = models.CharField(max_length=50, null=True, blank=True)

    # Area(s) of interest — multiple values stored as "|||"-joined labels (see FRT encodeAreasOfInterest).
    area_of_interest = models.TextField(null=True, blank=True)

    # Social Media
    social_instagram = models.URLField(max_length=255, null=True, blank=True)
    social_twitter = models.URLField(max_length=255, null=True, blank=True)
    social_tiktok = models.URLField(max_length=255, null=True, blank=True)
    social_youtube = models.URLField(max_length=255, null=True, blank=True)
    social_facebook = models.URLField(max_length=255, null=True, blank=True)
    social_linkedin = models.URLField(max_length=255, null=True, blank=True)
    social_other = models.JSONField(null=True, blank=True)

    # Profile Status
    status = models.CharField(max_length=20, choices=ProfileStatus.choices, default=ProfileStatus.INCOMPLETE)
    
    # Platform Trust
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    creator_tier = models.CharField(max_length=20, choices=CreatorTier.choices, default=CreatorTier.BRONZE)

    # Fan community
    fan_club_name = models.CharField(max_length=150, null=True, blank=True)
    welcome_message = models.TextField(null=True, blank=True)

    # Counters
    follower_count = models.IntegerField(default=0)
    subscriber_count = models.IntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=14, decimal_places=4, default=0.00)
    content_blocks_count = models.IntegerField(default=0)

    # Timestamps
    profile_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── CREATOR PLAN (CACHE COLUMNS) ──
    plan_tier = models.CharField(max_length=20, choices=CreatorPlanTier.choices, default=CreatorPlanTier.FREE)
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    live_credits = models.IntegerField(default=0)

    class Meta:
        db_table = "creator_profiles"
        app_label = "lipaidox_creator_profile"
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['status']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return f"{self.username} ({self.status})"
