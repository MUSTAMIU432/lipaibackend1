import uuid
from django.db import models

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="projects")
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    url = models.URLField(max_length=500, null=True, blank=True)
    github_url = models.URLField(max_length=500, null=True, blank=True)
    
    technologies = models.JSONField(default=list, blank=True) # Array of tech stack
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_student_projects"
        app_label = "lms_identity"

class ExternalCertification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="external_certifications")
    
    name = models.CharField(max_length=255)
    issuer = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    
    credential_id = models.CharField(max_length=255, null=True, blank=True)
    credential_url = models.URLField(max_length=500, null=True, blank=True)
    
    skills = models.JSONField(default=list, blank=True) # Array of skills verified
    
    class Meta:
        db_table = "lms_external_certifications"
        app_label = "lms_identity"
