import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from .category import PlatformCategory

class AudienceType(models.TextChoices):
    GENERAL = 'general', 'General'
    ADULT = 'adult', 'Adult'
    EDUCATIONAL = 'educational', 'Educational'
    FITNESS = 'fitness', 'Fitness'
    GAMING = 'gaming', 'Gaming'
    MUSIC = 'music', 'Music'
    TRAVEL = 'travel', 'Travel'
    OTHER = 'other', 'Other'

class GenderType(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'
    NON_BINARY = 'non_binary', 'Non-Binary'
    PREFER_NOT_TO_SAY = 'prefer_not_to_say', 'Prefer not to say'
    ALL = 'all', 'All Genders'

class AgeGapType(models.TextChoices):
    TEENS = 'teens', '13-17'
    YOUNG_ADULTS = 'young_adults', '18-24'
    ADULTS = 'adults', '25-34'
    MIDDLE_AGED = 'middle_aged', '35-49'
    MATURE = 'mature', '50-64'
    SENIORS = 'seniors', '65+'
    ALL_AGES = 'all_ages', 'All Ages'

class InterestType(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    SPORTS = 'sports', 'Sports'
    ARTS = 'arts', 'Arts & Culture'
    FASHION = 'fashion', 'Fashion'
    FOOD = 'food', 'Food & Cooking'
    PHOTOGRAPHY = 'photography', 'Photography'
    READING = 'reading', 'Reading'
    MOVIES = 'movies', 'Movies & TV'
    OUTDOORS = 'outdoors', 'Outdoors'
    PETS = 'pets', 'Pets & Animals'
    BUSINESS = 'business', 'Business'
    SCIENCE = 'science', 'Science'
    POLITICS = 'politics', 'Politics'
    DIY = 'diy', 'DIY & Crafts'
    COLLECTING = 'collecting', 'Collecting'
    GAMING = 'gaming', 'Gaming'
    SOCIAL = 'social', 'Social Media'
    MUSIC = 'music', 'Music'
    HEALTH = 'health', 'Health & Wellness'
    TRAVEL = 'travel', 'Travel'

class ProfessionalismType(models.TextChoices):
    CASUAL = 'casual', 'Casual'
    SEMI_PROFESSIONAL = 'semi_professional', 'Semi-Professional'
    PROFESSIONAL = 'professional', 'Professional'
    EXPERT = 'expert', 'Expert/Industry Leader'
    ALL_LEVELS = 'all_levels', 'All Levels'

class ContentClassification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="classification")
    
    # Primary Category (Stored as slug/string matching SQL spec)
    primary_category = models.CharField(max_length=100)
    
    # Secondary Categories (Array of slugs)
    secondary_categories = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    
    # Audience and Language (pipe-joined slugs from onboarding; max 3 enforced in mutations)
    audience_type = models.TextField(blank=True, default="general")
    content_language = models.CharField(max_length=50, default='en')
    
    # Target Audience Demographics
    target_gender = models.CharField(max_length=20, choices=GenderType.choices, default=GenderType.ALL)
    target_age_gap = models.CharField(max_length=20, choices=AgeGapType.choices, default=AgeGapType.ALL_AGES)
    target_country = models.CharField(max_length=100, blank=True, null=True)
    target_interests = ArrayField(models.CharField(max_length=50, choices=InterestType.choices), default=list, blank=True)
    target_professionalism = models.CharField(max_length=25, choices=ProfessionalismType.choices, default=ProfessionalismType.ALL_LEVELS)

    # Content Types
    has_images = models.BooleanField(default=False)
    has_videos = models.BooleanField(default=False)
    has_audio = models.BooleanField(default=False)
    has_live_streams = models.BooleanField(default=False)
    has_blog = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content_classifications"
        app_label = "lipaidox_cc"

    def __str__(self):
        return f"Classification for {self.creator}"
