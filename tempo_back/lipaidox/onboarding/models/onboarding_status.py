import uuid
from django.db import models
from django.utils import timezone
from multitenant.models import TenantAwareModel

class OnboardingStep(models.TextChoices):
    ACCOUNT_CREATED = 'account_created', 'Account Created'
    EMAIL_VERIFIED = 'email_verified', 'Email Verified'
    PHONE_VERIFIED = 'phone_verified', 'Phone Verified'
    PROFILE_SETUP = 'profile_setup', 'Profile Setup'
    CONTENT_CLASSIFICATION = 'content_classification', 'Content Classification'
    IDENTITY_VERIFICATION = 'identity_verification', 'Identity Verification'
    PAYMENT_SETUP = 'payment_setup', 'Payment Setup'
    MONETIZATION_SETUP = 'monetization_setup', 'Monetization Setup'

class StepStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'

class OnboardingOverallStatus(models.TextChoices):
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    SUSPENDED = 'suspended', 'Suspended'
    REJECTED = 'rejected', 'Rejected'

class CreatorOnboardingStatus(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField("lipaidox_auth.User", on_delete=models.CASCADE, related_name="onboarding_status")
    
    overall_status = models.CharField(max_length=20, choices=OnboardingOverallStatus.choices, default=OnboardingOverallStatus.IN_PROGRESS)
    current_step = models.CharField(max_length=50, choices=OnboardingStep.choices, default=OnboardingStep.ACCOUNT_CREATED)
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Step Statuses
    account_created_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.COMPLETED)
    account_created_at = models.DateTimeField(null=True, blank=True)

    email_verified_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    phone_verified_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    profile_setup_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    profile_setup_at = models.DateTimeField(null=True, blank=True)

    content_classification_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    content_classification_at = models.DateTimeField(null=True, blank=True)

    identity_verification_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    identity_verification_at = models.DateTimeField(null=True, blank=True)

    payment_setup_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    payment_setup_at = models.DateTimeField(null=True, blank=True)

    monetization_setup_status = models.CharField(max_length=20, choices=StepStatus.choices, default=StepStatus.NOT_STARTED)
    monetization_setup_at = models.DateTimeField(null=True, blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "creator_onboarding_status"
        app_label = "lipaidox_onboarding"

    def calculate_completion(self):
        statuses = [
            self.account_created_status, self.email_verified_status,
            self.phone_verified_status, self.profile_setup_status,
            self.content_classification_status, self.identity_verification_status,
            self.payment_setup_status, self.monetization_setup_status
        ]
        completed = len([s for s in statuses if s == StepStatus.COMPLETED])
        self.completion_percentage = (completed / 8) * 100
        if completed == 8:
            self.overall_status = OnboardingOverallStatus.COMPLETED
            if not self.completed_at:
                self.completed_at = timezone.now()
        self.save()
