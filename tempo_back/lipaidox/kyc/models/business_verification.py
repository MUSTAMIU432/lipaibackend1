import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .verification_document import DocumentType

class BusinessVerificationStatus(models.TextChoices):
    NOT_SUBMITTED = 'not_submitted', 'Not Submitted'
    PENDING = 'pending', 'Pending'
    AI_PROCESSING = 'ai_processing', 'AI Processing'
    ADMIN_REVIEW = 'admin_review', 'Admin Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    RESUBMISSION_REQUESTED = 'resubmission_requested', 'Resubmission Requested'
    PERMANENTLY_REJECTED = 'permanently_rejected', 'Permanently Rejected'

class BusinessType(models.TextChoices):
    SOLE_PROPRIETORSHIP = 'sole_proprietorship', 'Sole Proprietorship'
    PARTNERSHIP = 'partnership', 'Partnership'
    LLC = 'limited_liability_company', 'Limited Liability Company'
    CORPORATION = 'corporation', 'Corporation'
    NON_PROFIT = 'non_profit', 'Non Profit'
    AGENCY = 'agency', 'Agency'
    ENTERPRISE = 'enterprise', 'Enterprise'
    OTHER = 'other', 'Other'

class BusinessRejectionReason(models.TextChoices):
    INVALID_REGISTRATION_NUMBER = 'invalid_registration_number', 'Invalid Registration Number'
    BUSINESS_NOT_FOUND_IN_REGISTRY = 'business_not_found_in_registry', 'Business Not Found in Registry'
    EXPIRED_REGISTRATION = 'expired_registration', 'Expired Registration'
    NAME_MISMATCH = 'name_mismatch', 'Name Mismatch'
    INVALID_LICENSE = 'invalid_license', 'Invalid License'
    EXPIRED_LICENSE = 'expired_license', 'Expired License'
    INVALID_TIN = 'invalid_tin', 'Invalid TIN'
    INCOMPLETE_SUBMISSION = 'incomplete_submission', 'Incomplete Submission'
    DOCUMENT_TAMPERED = 'document_tampered', 'Document Tampered'
    SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
    OTHER = 'other', 'Other'

class BusinessVerification(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="business_verification")

    # Business Identity
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=50, choices=BusinessType.choices, default=BusinessType.OTHER)
    business_registration_number = models.CharField(max_length=100)
    registered_business_address = models.TextField(null=True, blank=True)
    business_website = models.URLField(max_length=500, null=True, blank=True)
    business_email = models.EmailField(max_length=255, null=True, blank=True)
    business_phone = models.CharField(max_length=20, null=True, blank=True)
    country_of_incorporation = models.CharField(max_length=100, null=True, blank=True)
    date_of_incorporation = models.DateField(null=True, blank=True)

    # Tax Information
    tin_number = models.CharField(max_length=100, null=True, blank=True)
    tin_certificate_url = models.URLField(max_length=1000, null=True, blank=True)
    tin_certificate_size_bytes = models.BigIntegerField(null=True, blank=True)
    tin_certificate_mime_type = models.CharField(max_length=100, null=True, blank=True)

    # Registration Document
    business_registration_doc_url = models.URLField(max_length=1000)
    business_registration_doc_size = models.BigIntegerField(null=True, blank=True)
    business_registration_doc_mime_type = models.CharField(max_length=100, null=True, blank=True)
    business_registration_expiry_date = models.DateField(null=True, blank=True)

    # Business License
    business_license_number = models.CharField(max_length=100, null=True, blank=True)
    business_license_url = models.URLField(max_length=1000, null=True, blank=True)
    business_license_size_bytes = models.BigIntegerField(null=True, blank=True)
    business_license_mime_type = models.CharField(max_length=100, null=True, blank=True)
    business_license_expiry_date = models.DateField(null=True, blank=True)

    # Certificate of Incorporation
    incorporation_certificate_url = models.URLField(max_length=1000, null=True, blank=True)
    incorporation_certificate_size_bytes = models.BigIntegerField(null=True, blank=True)
    incorporation_certificate_mime_type = models.CharField(max_length=100, null=True, blank=True)

    # Authorised Representative
    representative_first_name = models.CharField(max_length=100)
    representative_last_name = models.CharField(max_length=100)
    representative_role = models.CharField(max_length=100, null=True, blank=True)
    representative_id_document_url = models.URLField(max_length=1000, null=True, blank=True)
    representative_id_document_type = models.CharField(max_length=50, choices=DocumentType.choices, null=True, blank=True)
    representative_id_document_number = models.CharField(max_length=100, null=True, blank=True)
    representative_id_expiry_date = models.DateField(null=True, blank=True)
    representative_selfie_url = models.URLField(max_length=1000, null=True, blank=True)

    # AI Verification
    ai_registry_check_passed = models.BooleanField(null=True, blank=True)
    ai_registry_check_reason = models.TextField(null=True, blank=True)
    ai_document_valid = models.BooleanField(null=True, blank=True)
    ai_document_reason = models.TextField(null=True, blank=True)
    ai_fraud_flag = models.BooleanField(default=False)
    ai_fraud_reason = models.TextField(null=True, blank=True)
    ai_processed_at = models.DateTimeField(null=True, blank=True)

    # Admin Review
    verification_status = models.CharField(max_length=50, choices=BusinessVerificationStatus.choices, default=BusinessVerificationStatus.NOT_SUBMITTED)
    reviewed_by = models.ForeignKey("lipaidox_auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="business_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=100, choices=BusinessRejectionReason.choices, null=True, blank=True)
    rejection_note = models.TextField(null=True, blank=True)
    
    resubmission_count = models.IntegerField(default=0)
    max_resubmissions = models.IntegerField(default=3)
    last_resubmission_at = models.DateTimeField(null=True, blank=True)

    # Approval
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Permanent Rejection
    permanently_rejected_at = models.DateTimeField(null=True, blank=True)
    permanently_rejected_by = models.ForeignKey("lipaidox_auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="permanent_business_rejections")
    permanent_rejection_note = models.TextField(null=True, blank=True)

    # Timestamps
    first_submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "business_verifications"
        app_label = "lipaidox_kyc"
        indexes = [
            models.Index(fields=['verification_status']),
            models.Index(fields=['business_name']),
            models.Index(fields=['business_registration_number']),
        ]

    def __str__(self):
        return f"Business Verification - {self.business_name} ({self.verification_status})"
