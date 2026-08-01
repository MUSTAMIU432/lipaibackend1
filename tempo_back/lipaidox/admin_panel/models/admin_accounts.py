import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class AdminRole(models.TextChoices):
    """Admin role levels"""
    SUPERADMIN = 'superadmin', 'Super Admin'
    ADMIN = 'admin', 'Admin'
    MODERATOR = 'moderator', 'Moderator'
    SUPPORT = 'support', 'Support'
    FINANCE = 'finance', 'Finance'


class AdminActionCategory(models.TextChoices):
    """Categories of admin actions"""
    USER_MANAGEMENT = 'user_management', 'User Management'
    CONTENT_MODERATION = 'content_moderation', 'Content Moderation'
    KYC_REVIEW = 'kyc_review', 'KYC Review'
    FINANCIAL = 'financial', 'Financial'
    PLATFORM_SETTINGS = 'platform_settings', 'Platform Settings'
    ANNOUNCEMENT = 'announcement', 'Announcement'
    CREDIT_MANAGEMENT = 'credit_management', 'Credit Management'
    ACCOUNT_FLAG = 'account_flag', 'Account Flag'
    REPORT_RESOLUTION = 'report_resolution', 'Report Resolution'


class AdminActionType(models.TextChoices):
    """Specific types of admin actions"""
    # User management
    USER_SUSPENDED = 'user_suspended', 'User Suspended'
    USER_BANNED = 'user_banned', 'User Banned'
    USER_ACTIVATED = 'user_activated', 'User Activated'
    USER_DEACTIVATED = 'user_deactivated', 'User Deactivated'
    USER_ROLE_CHANGED = 'user_role_changed', 'User Role Changed'
    USER_PASSWORD_RESET = 'user_password_reset', 'User Password Reset'

    # KYC
    KYC_APPROVED = 'kyc_approved', 'KYC Approved'
    KYC_REJECTED = 'kyc_rejected', 'KYC Rejected'
    KYC_RESUBMISSION_REQUESTED = 'kyc_resubmission_requested', 'KYC Resubmission Requested'
    KYC_PERMANENTLY_REJECTED = 'kyc_permanently_rejected', 'KYC Permanently Rejected'

    # Content
    CONTENT_REMOVED = 'content_removed', 'Content Removed'
    CONTENT_FLAGGED = 'content_flagged', 'Content Flagged'
    CONTENT_APPROVED = 'content_approved', 'Content Approved'
    CONTENT_RESTORED = 'content_restored', 'Content Restored'

    # Financial
    PAYOUT_APPROVED = 'payout_approved', 'Payout Approved'
    PAYOUT_REJECTED = 'payout_rejected', 'Payout Rejected'
    PAYOUT_REVERSED = 'payout_reversed', 'Payout Reversed'
    CREDIT_GIFTED = 'credit_gifted', 'Credit Gifted'
    FEE_OVERRIDDEN = 'fee_overridden', 'Fee Overridden'

    # Account
    ACCOUNT_FLAGGED = 'account_flagged', 'Account Flagged'
    ACCOUNT_FLAG_RESOLVED = 'account_flag_resolved', 'Account Flag Resolved'
    ACCOUNT_FLAG_DISMISSED = 'account_flag_dismissed', 'Account Flag Dismissed'

    # Report
    REPORT_RESOLVED = 'report_resolved', 'Report Resolved'
    REPORT_DISMISSED = 'report_dismissed', 'Report Dismissed'
    REPORT_ESCALATED = 'report_escalated', 'Report Escalated'

    # Platform
    ANNOUNCEMENT_CREATED = 'announcement_created', 'Announcement Created'
    ANNOUNCEMENT_UPDATED = 'announcement_updated', 'Announcement Updated'
    ANNOUNCEMENT_DELETED = 'announcement_deleted', 'Announcement Deleted'
    PLATFORM_POST_CREATED = 'platform_post_created', 'Platform Post Created'
    PLATFORM_POST_REMOVED = 'platform_post_removed', 'Platform Post Removed'
    PLATFORM_SETTINGS_UPDATED = 'platform_settings_updated', 'Platform Settings Updated'


class AdminAccount(TenantAwareModel):
    """
    Admin accounts - users with role='admin' get extra details here
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="admin_account"
    )
    admin_role = models.CharField(max_length=20, choices=AdminRole.choices, default=AdminRole.MODERATOR)
    display_name = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # Permissions
    can_manage_kyc = models.BooleanField(default=False)
    can_manage_financials = models.BooleanField(default=False)
    can_manage_content = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_post_announcements = models.BooleanField(default=False)
    can_gift_credits = models.BooleanField(default=False)

    last_active_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_accounts"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['admin_role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.display_name or self.user.username} ({self.admin_role})"


class AdminAction(TenantAwareModel):
    """
    Audit trail of all admin actions - append-only, never updated
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        AdminAccount,
        on_delete=models.CASCADE,
        related_name="actions"
    )

    # Targets
    acted_on_user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.SET_NULL,
        related_name="admin_actions_taken_on",
        null=True,
        blank=True
    )
    acted_on_content = models.ForeignKey(
        "lipaidox_content.Content",
        on_delete=models.SET_NULL,
        related_name="admin_actions_taken_on",
        null=True,
        blank=True
    )
    acted_on_entity_id = models.UUIDField(null=True, blank=True)
    acted_on_entity_type = models.CharField(max_length=100, blank=True, null=True)

    # Action details
    category = models.CharField(max_length=30, choices=AdminActionCategory.choices)
    action_type = models.CharField(max_length=30, choices=AdminActionType.choices)
    reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    # State snapshots
    state_before = models.JSONField(default=dict, blank=True)
    state_after = models.JSONField(default=dict, blank=True)

    # Reversibility
    is_reversible = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        AdminAccount,
        on_delete=models.SET_NULL,
        related_name="reversed_actions",
        null=True,
        blank=True
    )
    reversal_reason = models.TextField(blank=True, null=True)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_actions"
        app_label = "lipaidox_admin_panel"
        indexes = [
            models.Index(fields=['admin']),
            models.Index(fields=['acted_on_user']),
            models.Index(fields=['acted_on_content']),
            models.Index(fields=['action_type']),
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(reversed_at__isnull=True) | models.Q(is_reversible=True),
                name='reversal_check'
            ),
        ]

    def __str__(self):
        return f"{self.action_type} by {self.admin} at {self.created_at}"
