import uuid
from django.db import models

class WorkExperience(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="experiences")
    
    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    location = models.CharField(max_length=255, null=True, blank=True)
    location_type = models.CharField(max_length=20, choices=[('remote', 'Remote'), ('hybrid', 'Hybrid'), ('onsite', 'On-Site')], default='onsite')
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    
    description = models.TextField(null=True, blank=True)
    achievements = models.JSONField(default=list, blank=True) # List of bullet points
    skills = models.JSONField(default=list, blank=True) # List of skills used
    
    class Meta:
        db_table = "lms_work_experiences"
        app_label = "lms_identity"
        ordering = ['-start_date']

class EducationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="education")
    
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255)
    location = models.CharField(max_length=255, null=True, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_education_records"
        app_label = "lms_identity"
        ordering = ['-start_date']
