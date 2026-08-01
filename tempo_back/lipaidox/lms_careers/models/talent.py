import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class TalentPoolProfile(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="talent_profile")
    
    is_visible = models.BooleanField(default=True)
    bio = models.TextField(null=True, blank=True)
    skills = models.JSONField(default=list) # Array of skills
    
    desired_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    availability = models.CharField(max_length=100, default="Immediately")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_talent_pool_profiles"
        app_label = "lms_careers"

    def __str__(self):
        return f"Talent: {self.student.user.username}"
