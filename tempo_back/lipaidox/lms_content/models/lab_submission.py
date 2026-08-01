import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class LabSubmissionStatus(models.TextChoices):
    SUBMITTED = 'submitted', 'Submitted'
    GRADING = 'grading', 'Grading'
    PASSED = 'passed', 'Passed'
    FAILED = 'failed', 'Failed'
    RESUBMITTED = 'resubmitted', 'Resubmitted'

class LabSubmission(TenantAwareModel):
    """
    Student lab submissions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lab = models.ForeignKey(
        "Lab",
        on_delete=models.CASCADE,
        related_name="submissions"
    )
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="lab_submissions"
    )
    
    # Submission content
    code = models.TextField()
    language = models.CharField(max_length=50, default="python")
    
    # Execution results
    output = models.TextField(null=True, blank=True)
    error_output = models.TextField(null=True, blank=True)
    
    # Grading
    is_passing = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    
    status = models.CharField(
        max_length=20,
        choices=LabSubmissionStatus.choices,
        default=LabSubmissionStatus.SUBMITTED
    )
    
    # Feedback
    instructor_feedback = models.TextField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_lab_submissions"
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    
    # Execution metrics
    execution_time_ms = models.IntegerField(null=True, blank=True)
    memory_usage_mb = models.FloatField(null=True, blank=True)
    test_results = models.JSONField(default=dict, blank=True)  # Test case results
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_lab_submissions"
        app_label = "lms_content"
        unique_together = ('lab', 'student')
        indexes = [
            models.Index(fields=['lab'], name='idx_lab_submission_lab'),
            models.Index(fields=['student'], name='idx_lab_submission_student'),
            models.Index(fields=['status'], name='idx_lab_submission_status'),
            models.Index(fields=['-submitted_at'], name='idx_lab_submission_submitted'),
        ]
    
    def __str__(self):
        return f"{self.student.user.username} - {self.lab.title}"
    
    def grade_submission(self, graded_by, score, is_passing, feedback=None):
        """Grade the submission"""
        self.graded_by = graded_by
        self.score = score
        self.is_passing = is_passing
        self.instructor_feedback = feedback
        self.status = LabSubmissionStatus.PASSED if is_passing else LabSubmissionStatus.FAILED
        from django.utils import timezone
        self.graded_at = timezone.now()
        self.save()
    
    def resubmit(self, new_code):
        """Create a resubmission"""
        self.code = new_code
        self.status = LabSubmissionStatus.RESUBMITTED
        self.is_passing = False
        self.score = None
        self.instructor_feedback = None
        self.graded_by = None
        self.graded_at = None
        self.output = None
        self.error_output = None
        self.test_results = {}
        self.save()
    
    @classmethod
    def get_best_submission(cls, lab, student):
        """Get the best submission for a lab-student pair"""
        return cls.objects.filter(lab=lab, student=student).order_by('-score', '-submitted_at').first()
    
    @classmethod
    def get_submission_stats(cls, lab):
        """Get submission statistics for a lab"""
        from django.db.models import Count, Avg, Q
        return cls.objects.filter(lab=lab).aggregate(
            total_submissions=Count('id'),
            passed_count=Count('id', filter=Q(is_passing=True)),
            failed_count=Count('id', filter=Q(is_passing=False)),
            average_score=Avg('score'),
        )
