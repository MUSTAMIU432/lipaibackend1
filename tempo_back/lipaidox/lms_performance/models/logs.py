import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class ActivityAction(models.TextChoices):
    START = 'start', 'Start'
    PAUSE = 'pause', 'Pause'
    COMPLETE = 'complete', 'Complete'
    QUIZ_ATTEMPT = 'quiz_attempt', 'Quiz Attempt'

class LearningActivityLog(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="activity_logs")
    
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE)
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE, null=True, blank=True)
    
    action = models.CharField(max_length=20, choices=ActivityAction.choices)
    duration_seconds = models.IntegerField(default=0)
    
    logged_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "lms_learning_activity_logs"
        app_label = "lms_performance"
        ordering = ['-logged_at']

    def __str__(self):
        return f"{self.student.user.username} - {self.action} - {self.course.title}"
