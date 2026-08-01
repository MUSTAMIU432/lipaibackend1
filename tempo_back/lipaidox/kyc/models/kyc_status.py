import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .verification_document import KYCType

class KYCOverallStatus(models.TextChoices):
    NOT_SUBMITTED = 'not_submitted', 'Not Submitted'
    PENDING = 'pending', 'Pending'
    AI_PROCESSING = 'ai_processing', 'AI Processing'
    ADMIN_REVIEW = 'admin_review', 'Admin Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    RESUBMISSION_REQUESTED = 'resubmission_requested', 'Resubmission Requested'
    PERMANENTLY_REJECTED = 'permanently_rejected', 'Permanently Rejected'

class KYCRejectionReason(models.TextChoices):
    DOCUMENT_EXPIRED = 'document_expired', 'Document Expired'
    DOCUMENT_BLURRY = 'document_blurry', 'Document Blurry'
    DOCUMENT_TAMPERED = 'document_tampered', 'Document Tampered'
    FACE_MISMATCH = 'face_mismatch', 'Face Mismatch'
    DUPLICATE_IDENTITY = 'duplicate_identity', 'Duplicate Identity'
    INVALID_DOCUMENT_TYPE = 'invalid_document_type', 'Invalid Document Type'
    INCOMPLETE_SUBMISSION = 'incomplete_submission', 'Incomplete Submission'
    SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
    BUSINESS_NOT_REGISTERED = 'business_not_registered', 'Business Not Registered'
    OTHER = 'other', 'Other'

class KYCStatus(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="kyc_status")
    kyc_type = models.CharField(max_length=20, choices=KYCType.choices, default=KYCType.INDIVIDUAL)

    # Current State
    overall_status = models.CharField(max_length=50, choices=KYCOverallStatus.choices, default=KYCOverallStatus.NOT_SUBMITTED)
    current_document = models.ForeignKey("lipaidox_kyc.VerificationDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="active_for_status")

    # Resubmission Tracking
    resubmission_count = models.IntegerField(default=0)
    max_resubmissions = models.IntegerField(default=3)
    last_resubmission_at = models.DateTimeField(null=True, blank=True)

    # Admin Review
    reviewed_by = models.ForeignKey("lipaidox_auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="kyc_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=100, choices=KYCRejectionReason.choices, null=True, blank=True)
    rejection_note = models.TextField(null=True, blank=True)

    # Approval
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Permanent Rejection
    permanently_rejected_at = models.DateTimeField(null=True, blank=True)
    permanently_rejected_by = models.ForeignKey("lipaidox_auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="permanent_rejections")
    permanent_rejection_note = models.TextField(null=True, blank=True)

    # Timestamps
    first_submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "kyc_status"
        app_label = "lipaidox_kyc"
        indexes = [
            models.Index(fields=['overall_status']),
            models.Index(fields=['reviewed_by']),
            models.Index(fields=['approved_at']),
        ]

    def __str__(self):
        return f"KYC Status ({self.overall_status}) - {self.creator}"
