import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class LearningPath(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Career/Skill focus
    skills = models.JSONField(default=list, blank=True) # Array of skills this path builds
    course_ids = models.JSONField(default=list, blank=True) # Array of UUIDs in order
    
    estimated_duration_weeks = models.IntegerField(default=12)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_learning_paths"
        app_label = "lms_content"

    def __str__(self):
        return self.title
