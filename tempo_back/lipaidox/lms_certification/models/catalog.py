import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class CertificateType(models.TextChoices):
    PROFESSIONAL = 'professional', 'Professional Certificate'
    COMPLETION = 'completion', 'Certificate of Completion'
    MASTERY = 'skill_mastery', 'Skill Mastery'

class AvailableCertification(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    provider = models.CharField(max_length=255) # e.g., Lipaidox Academy, Industry Partner
    
    cert_type = models.CharField(max_length=20, choices=CertificateType.choices, default=CertificateType.PROFESSIONAL)
    difficulty = models.CharField(max_length=20, default="intermediate")
    estimated_hours = models.IntegerField(default=0)
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default="USD")
    
    requirements = models.JSONField(default=list) # List of course IDs or strings
    skills = models.JSONField(default=list) # List of skills to be earned
    
    enrolled_count = models.IntegerField(default=0)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_available_certifications"
        app_label = "lms_certification"

class CertificationEnrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="cert_enrollments")
    certification = models.ForeignKey(AvailableCertification, on_delete=models.CASCADE, related_name="enrolled_students")
    
    progress_percent = models.IntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_certification_enrollments"
        app_label = "lms_certification"
        unique_together = ('student', 'certification')
