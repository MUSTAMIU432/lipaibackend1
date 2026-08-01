import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class JobType(models.TextChoices):
    REMOTE = 'remote', 'Remote'
    HYBRID = 'hybrid', 'Hybrid'
    ONSITE = 'onsite', 'On-Site'

class JobStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'
    DRAFT = 'draft', 'Draft'

class JobListing(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employer = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="job_listings")
    
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.REMOTE)
    
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD")
    
    description = models.TextField()
    required_skills = models.JSONField(default=list) # Array of skills
    
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_job_listings"
        app_label = "lms_careers"

    def __str__(self):
        return f"{self.title} at {self.company}"
