import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    COMPLETED = 'completed', 'Completed'
    REFUNDED = 'refunded', 'Refunded'

class Enrollment(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE, related_name="students_enrolled")
    
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    progress_percent = models.IntegerField(default=0)
    
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_enrollments"
        app_label = "lms_learning"
        unique_together = ('student', 'course')
