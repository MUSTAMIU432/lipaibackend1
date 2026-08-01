import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .course import Course

class Recommendation(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="recommendations")
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    priority = models.CharField(max_length=20, choices=[('high', 'High'), ('low', 'Low')], default='low')
    reasons = models.JSONField(default=list, blank=True) # E.g., ['Based on your skills', 'Popular in your area']
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_recommendations"
        app_label = "lms_content"
        unique_together = ('student', 'course')
