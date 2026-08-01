import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from multitenant.models import TenantAwareModel


class ReportReason(models.TextChoices):
    """Reasons for reporting content - Module 18 spec"""
    SPAM = 'spam', 'Spam'
    MISINFORMATION = 'misinformation', 'Misinformation'
    HARASSMENT = 'harassment', 'Harassment'
    HATE_SPEECH = 'hate_speech', 'Hate Speech'
    EXPLICIT_CONTENT = 'explicit_content', 'Explicit Content'
    COPYRIGHT_VIOLATION = 'copyright_violation', 'Copyright Violation'
    SCAM = 'scam', 'Scam'
    IMPERSONATION = 'impersonation', 'Impersonation'
    SELF_HARM = 'self_harm', 'Self Harm'
    VIOLENCE = 'violence', 'Violence'
    ILLEGAL_CONTENT = 'illegal_content', 'Illegal Content'
    OTHER = 'other', 'Other'


class ReportStatus(models.TextChoices):
    """Status of content reports - Module 18 spec"""
    PENDING = 'pending', 'Pending'
    UNDER_REVIEW = 'under_review', 'Under Review'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'
    ESCALATED = 'escalated', 'Escalated'


class ReportResolution(models.TextChoices):
    """Resolution types for reports - Module 18 spec"""
    CONTENT_REMOVED = 'content_removed', 'Content Removed'
    CONTENT_APPROVED = 'content_approved', 'Content Approved'
    CREATOR_WARNED = 'creator_warned', 'Creator Warned'
    CREATOR_SUSPENDED = 'creator_suspended', 'Creator Suspended'
    CREATOR_BANNED = 'creator_banned', 'Creator Banned'
    NO_ACTION = 'no_action', 'No Action'
    ESCALATED_TO_LEGAL = 'escalated_to_legal', 'Escalated to Legal'


class ContentReport(TenantAwareModel):
    """
    Content reporting system - Module 18 implementation
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # References
    content = models.ForeignKey(
        "lipaidox_content.Content",
        on_delete=models.CASCADE,
        related_name="reports"
    )
    reported_by = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="content_reports",
        null=True,
        blank=True
    )
    creator = models.ForeignKey(
        "lipaidox_creator_profile.CreatorProfile",
        on_delete=models.CASCADE,
        related_name="content_reports_received",
        null=True,
        blank=True
    )

    # Report details
    reason = models.CharField(max_length=30, choices=ReportReason.choices)
    description = models.TextField(blank=True, null=True)
    evidence_urls = ArrayField(
        models.URLField(max_length=2000),
        default=list,
        blank=True
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING
    )

    # Review
    reviewed_by = models.ForeignKey(
        "lipaidox_admin_panel.AdminAccount",
        on_delete=models.SET_NULL,
        related_name="reports_reviewed",
        null=True,
        blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(
        max_length=30,
        choices=ReportResolution.choices,
        blank=True,
        null=True
    )
    resolution_note = models.TextField(blank=True, null=True)

    # Escalation
    escalated_by = models.ForeignKey(
        "lipaidox_admin_panel.AdminAccount",
        on_delete=models.SET_NULL,
        related_name="reports_escalated",
        null=True,
        blank=True
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content_reports"
        app_label = "lipaidox_content"
        indexes = [
            models.Index(fields=['content']),
            models.Index(fields=['reported_by']),
            models.Index(fields=['creator']),
            models.Index(fields=['status']),
            models.Index(fields=['reason']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            # A user can only report the same content once
            models.UniqueConstraint(
                fields=['content', 'reported_by'],
                name='content_reports_unique'
            ),
        ]

    def __str__(self):
        return f"Report by {self.reported_by.username} on {self.content.id} - {self.status}"


class ContentModerationLog(TenantAwareModel):
    """
    Log of moderation actions taken on content
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        "lipaidox_content.Content",
        on_delete=models.CASCADE,
        related_name="moderation_logs"
    )
    moderator = models.ForeignKey(
        "lipaidox_admin_panel.AdminAccount",
        on_delete=models.CASCADE,
        related_name="moderation_actions"
    )
    action = models.CharField(max_length=100)
    reason = models.TextField()
    related_report = models.ForeignKey(
        ContentReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_action"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_moderation_logs"
        app_label = "lipaidox_content"
        ordering = ['-created_at']

    def __str__(self):
        return f"Moderation: {self.action} on {self.content.id} by {self.moderator}"
