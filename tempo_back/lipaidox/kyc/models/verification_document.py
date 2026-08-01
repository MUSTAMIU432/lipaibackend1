import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class KYCType(models.TextChoices):
    INDIVIDUAL = 'individual', 'Individual'
    BUSINESS = 'business', 'Business'

class DocumentType(models.TextChoices):
    PASSPORT = 'passport', 'Passport'
    NATIONAL_ID = 'national_id', 'National ID'
    DRIVER_LICENSE = 'driver_license', 'Driver License'
    OTHER = 'other', 'Other'

class DocumentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    AI_PROCESSING = 'ai_processing', 'AI Processing'
    AI_PASSED = 'ai_passed', 'AI Passed'
    AI_FAILED = 'ai_failed', 'AI Failed'
    ADMIN_REVIEW = 'admin_review', 'Admin Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    RESUBMISSION_REQUESTED = 'resubmission_requested', 'Resubmission Requested'
    EXPIRED = 'expired', 'Expired'

class VerificationDocument(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="verification_documents")
    kyc_type = models.CharField(max_length=20, choices=KYCType.choices, default=KYCType.INDIVIDUAL)

    # Individual Fields
    document_type = models.CharField(max_length=50, choices=DocumentType.choices, null=True, blank=True)
    # Free-text name used when document_type = 'other' (e.g. "NSSF Card")
    document_name = models.CharField(max_length=200, null=True, blank=True)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    document_expiry_date = models.DateField(null=True, blank=True)
    document_file_url = models.URLField(max_length=1000, null=True, blank=True)
    document_file_size_bytes = models.BigIntegerField(null=True, blank=True)
    document_mime_type = models.CharField(max_length=100, null=True, blank=True)

    # Selfie
    selfie_url = models.URLField(max_length=1000, null=True, blank=True)
    selfie_file_size_bytes = models.BigIntegerField(null=True, blank=True)

    # TIN
    tin_number = models.CharField(max_length=100, null=True, blank=True)
    tin_certificate_url = models.URLField(max_length=1000, null=True, blank=True)
    tin_file_size_bytes = models.BigIntegerField(null=True, blank=True)
    tin_mime_type = models.CharField(max_length=100, null=True, blank=True)

    # Business Fields
    business_name = models.CharField(max_length=255, null=True, blank=True)
    business_registration_number = models.CharField(max_length=100, null=True, blank=True)
    business_registration_doc_url = models.URLField(max_length=1000, null=True, blank=True)
    business_registration_doc_size = models.BigIntegerField(null=True, blank=True)
    business_registration_mime_type = models.CharField(max_length=100, null=True, blank=True)

    # AI Verification
    ai_face_match_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    ai_fraud_flag = models.BooleanField(default=False)
    ai_fraud_reason = models.TextField(null=True, blank=True)
    ai_document_valid = models.BooleanField(null=True, blank=True)
    ai_document_reason = models.TextField(null=True, blank=True)
    ai_processed_at = models.DateTimeField(null=True, blank=True)

    # Document Status
    status = models.CharField(max_length=50, choices=DocumentStatus.choices, default=DocumentStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "verification_documents"
        app_label = "lipaidox_kyc"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['kyc_type']),
            models.Index(fields=['submitted_at']),
        ]

    def __str__(self):
        return f"KYC Document ({self.kyc_type}) - {self.creator}"
