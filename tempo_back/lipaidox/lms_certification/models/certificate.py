import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class CertificateType(models.TextChoices):
    PROFESSIONAL = 'professional', 'Professional Certificate'
    COMPLETION = 'completion', 'Certificate of Completion'
    MASTERY = 'skill_mastery', 'Skill Mastery'

class CertificateGrade(models.TextChoices):
    DISTINCTION = 'distinction', 'Distinction'
    MERIT = 'merit', 'Merit'
    HONORS = 'honors', 'Honors'
    PASS = 'pass', 'Pass'

class Certificate(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey("lms_content.Course", on_delete=models.SET_NULL, null=True, blank=True)
    
    title = models.CharField(max_length=255)
    certificate_type = models.CharField(max_length=20, choices=CertificateType.choices, default=CertificateType.COMPLETION)
    grade = models.CharField(max_length=20, choices=CertificateGrade.choices, default=CertificateGrade.PASS)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    issue_date = models.DateTimeField(auto_now_add=True)
    verification_code = models.CharField(max_length=100, unique=True)
    public_url = models.URLField(max_length=500, null=True, blank=True)
    qr_code_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Blockchain Verification
    blockchain_hash = models.CharField(max_length=255, null=True, blank=True)
    blockchain_network = models.CharField(max_length=100, default="Polygon")
    
    is_public = models.BooleanField(default=True)
    view_count = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)

    class Meta:
        db_table = "lms_certificates"
        app_label = "lms_certification"

    def __str__(self):
        return f"{self.title} - {self.student.user.username}"
