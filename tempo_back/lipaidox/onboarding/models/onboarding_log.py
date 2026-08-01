import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .onboarding_status import OnboardingStep, StepStatus

class LogEventType(models.TextChoices):
    STEP_STARTED = 'step_started', 'Step Started'
    STEP_COMPLETED = 'step_completed', 'Step Completed'
    STEP_FAILED = 'step_failed', 'Step Failed'
    STEP_RETRIED = 'step_retried', 'Step Retried'
    STEP_SKIPPED = 'step_skipped', 'Step Skipped'
    DOCUMENT_UPLOADED = 'document_uploaded', 'Document Uploaded'
    DOCUMENT_REJECTED = 'document_rejected', 'Document Rejected'
    DOCUMENT_RESUBMITTED = 'document_resubmitted', 'Document Resubmitted'
    ADMIN_APPROVED = 'admin_approved', 'Admin Approved'
    ADMIN_REJECTED = 'admin_rejected', 'Admin Rejected'
    ADMIN_REQUESTED_RESUBMISSION = 'admin_requested_resubmission', 'Admin Requested Resubmission'

class OnboardingStepLog(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="onboarding_logs")
    onboarding = models.ForeignKey("lipaidox_onboarding.CreatorOnboardingStatus", on_delete=models.CASCADE, related_name="logs")
    
    step = models.CharField(max_length=50, choices=OnboardingStep.choices)
    event_type = models.CharField(max_length=50, choices=LogEventType.choices)
    
    status_before = models.CharField(max_length=20, choices=StepStatus.choices, null=True, blank=True)
    status_after = models.CharField(max_length=20, choices=StepStatus.choices, null=True, blank=True)
    
    triggered_by = models.CharField(max_length=20, choices=[('creator', 'Creator'), ('admin', 'Admin'), ('system', 'System')])
    actor = models.ForeignKey("lipaidox_auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="action_logs")
    
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "onboarding_step_logs"
        app_label = "lipaidox_onboarding"
