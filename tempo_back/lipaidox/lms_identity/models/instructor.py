import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class InstructorStatus(models.TextChoices):
    PENDING = 'pending_review', 'Pending Review'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    REJECTED = 'rejected', 'Rejected'

class InstructorProfile(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="instructor_profile")
    
    # Link to Platform Creator Profile (if exists)
    creator_profile = models.ForeignKey(
        "lipaidox_creator_profile.CreatorProfile", 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name="lms_instructor"
    )

    bio = models.TextField(null=True, blank=True)
    headline = models.CharField(max_length=255, null=True, blank=True)
    specializations = models.JSONField(default=list, blank=True)
    
    # Stats (Denormalized)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.IntegerField(default=0)
    total_students = models.IntegerField(default=0)
    total_courses = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=InstructorStatus.choices, default=InstructorStatus.PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_instructor_profiles"
        app_label = "lms_identity"
