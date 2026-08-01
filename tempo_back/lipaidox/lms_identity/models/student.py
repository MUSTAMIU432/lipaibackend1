import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class EmploymentStatus(models.TextChoices):
    EMPLOYED = 'employed', 'Employed'
    SELF_EMPLOYED = 'self_employed', 'Self-Employed'
    STUDENT = 'student', 'Student'
    UNEMPLOYED = 'unemployed', 'Unemployed'
    FREELANCER = 'freelancer', 'Freelancer'

class LocationType(models.TextChoices):
    REMOTE = 'remote', 'Remote'
    HYBRID = 'hybrid', 'Hybrid'
    ONSITE = 'onsite', 'On-site'

class SkillLevel(models.TextChoices):
    BEGINNER = 'beginner', 'Beginner'
    INTERMEDIATE = 'intermediate', 'Intermediate'
    ADVANCED = 'advanced', 'Advanced'
    EXPERT = 'expert', 'Expert'

class StudentProfile(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")

    # Full Profile Information (UI Driven)
    headline = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    
    # Social Proof (New)
    website = models.URLField(max_length=500, null=True, blank=True)
    linkedin = models.URLField(max_length=500, null=True, blank=True)
    github = models.URLField(max_length=500, null=True, blank=True)
    portfolio = models.URLField(max_length=500, null=True, blank=True)
    
    # Career Goals from Onboarding
    employment_status = models.CharField(max_length=50, choices=EmploymentStatus.choices, null=True)
    years_of_experience = models.IntegerField(default=0)
    career_goals = models.JSONField(default=list, blank=True) # Array of goals
    desired_roles = models.JSONField(default=list, blank=True) # Array of roles
    
    # Preferences (New)
    remote_preference = models.BooleanField(default=False)
    willing_to_relocate = models.BooleanField(default=False)
    learning_preferences = models.JSONField(default=dict, blank=True) # e.g. self-paced, video-first, etc.
    
    # Tracking
    onboarding_completed = models.BooleanField(default=False)
    onboarding_step = models.IntegerField(default=1)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    # Denormalized Metrics
    total_courses_enrolled = models.IntegerField(default=0)
    total_courses_completed = models.IntegerField(default=0)
    total_learning_mins = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_student_profiles"
        app_label = "lms_identity"

    def __str__(self):
        return f"Student: {self.user.username}"
