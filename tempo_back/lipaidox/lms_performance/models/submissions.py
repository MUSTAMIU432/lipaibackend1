import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class QuizAttempt(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="quiz_attempts")
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE)
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE, null=True, blank=True)
    
    answers = models.JSONField(default=list) # [{question_id: 1, chosen: 'A'}]
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    passed = models.BooleanField(default=False)
    
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_quiz_attempts"
        app_label = "lms_performance"
        ordering = ['-attempted_at']

class AssignmentSubmission(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="assignment_submissions")
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE)
    
    file_url = models.URLField(max_length=500, null=True, blank=True)
    text_content = models.TextField(null=True, blank=True)
    
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "lms_assignment_submissions"
        app_label = "lms_performance"
        ordering = ['-submitted_at']
