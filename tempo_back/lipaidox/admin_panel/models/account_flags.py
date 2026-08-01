import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class FlagReason(models.TextChoices):
    """Reasons for flagging an account"""
    SUSPECTED_FRAUD = 'suspected_fraud', 'Suspected Fraud'
    IDENTITY_MISMATCH = 'identity_mismatch', 'Identity Mismatch'
    DUPLICATE_ACCOUNT = 'duplicate_account', 'Duplicate Account'
    POLICY_VIOLATION = 'policy_violation', 'Policy Violation'
    PAYMENT_FRAUD = 'payment_fraud', 'Payment Fraud'
    CONTENT_VIOLATION = 'content_violation', 'Content Violation'
    SPAM_BEHAVIOUR = 'spam_behaviour', 'Spam Behaviour'
    AML_CONCERN = 'aml_concern', 'AML Concern'
    CHARGEBACK_ABUSE = 'chargeback_abuse', 'Chargeback Abuse'
    SUSPICIOUS_LOGIN = 'suspicious_login', 'Suspicious Login'
    OTHER = 'other', 'Other'


class FlagSeverity(models.TextChoices):
    """Severity levels for account flags"""
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'


class FlagStatus(models.TextChoices):
    """Status of account flags"""
    OPEN = 'open', 'Open'
    UNDER_INVESTIGATION = 'under_investigation', 'Under Investigation'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'
    ESCALATED = 'escalated', 'Escalated'


class FlagResolution(models.TextChoices):
    """Resolution types for account flags"""
    NO_ACTION = 'no_action', 'No Action'
    WARNING_ISSUED = 'warning_issued', 'Warning Issued'
    ACCOUNT_RESTRICTED = 'account_restricted', 'Account Restricted'
    ACCOUNT_SUSPENDED = 'account_suspended', 'Account Suspended'
    ACCOUNT_BANNED = 'account_banned', 'Account Banned'
    REFERRED_TO_LEGAL = 'referred_to_legal', 'Referred to Legal'
    FALSE_POSITIVE = 'false_positive', 'False Positive'


class AccountFlag(TenantAwareModel):
    """
    Account flags for fraud detection and policy violations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flagged_user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="account_flags"
    )

    # Flag details
    reason = models.CharField(max_length=30, choices=FlagReason.choices)
    severity = models.CharField(max_length=20, choices=FlagSeverity.choices, default=FlagSeverity.MEDIUM)
    description = models.TextField(blank=True, null=True)
    evidence = models.JSONField(default=dict, blank=True)

    # Source
    flagged_by_admin = models.ForeignKey(
        "AdminAccount",
        on_delete=models.SET_NULL,
        related_name="flags_created",
        null=True,
        blank=True
    )
    flagged_by_system = models.BooleanField(default=False)
    system_trigger = models.CharField(max_length=255, blank=True, null=True)

    # Status
    status = models.CharField(max_length=30, choices=FlagStatus.choices, default=FlagStatus.OPEN)

    # Investigation
    assigned_to = models.ForeignKey(
        "AdminAccount",
        on_delete=models.SET_NULL,
        related_name="flags_assigned",
        null=True,
        blank=True
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    investigation_notes = models.TextField(blank=True, null=True)

    # Resolution
    resolved_by = models.ForeignKey(
        "AdminAccount",
        on_delete=models.SET_NULL,
        related_name="flags_resolved",
        null=True,
        blank=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=30, choices=FlagResolution.choices, blank=True, null=True)
    resolution_note = models.TextField(blank=True, null=True)

    # Escalation
    escalated_by = models.ForeignKey(
        "AdminAccount",
        on_delete=models.SET_NULL,
        related_name="flags_escalated",
        null=True,
        blank=True
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_flags"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['flagged_user']),
            models.Index(fields=['reason']),
            models.Index(fields=['severity']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Flag on {self.flagged_user.username}: {self.reason} ({self.status})"
