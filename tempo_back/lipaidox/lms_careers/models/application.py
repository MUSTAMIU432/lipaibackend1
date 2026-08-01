import uuid
from django.db import models
from .job import JobListing

class ApplicationStatus(models.TextChoices):
    APPLIED = 'applied', 'Applied'
    VIEWED = 'viewed', 'Viewed'
    SHORTLISTED = 'shortlisted', 'Shortlisted'
    REJECTED = 'rejected', 'Rejected'
    HIRED = 'hired', 'Hired'

class JobApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="job_applications")
    job = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name="applications")
    
    resume_url = models.URLField(max_length=500)
    cover_letter = models.TextField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_job_applications"
        app_label = "lms_careers"
        unique_together = ('student', 'job')

    def __str__(self):
        return f"{self.student.user.username} - {self.job.title}"
