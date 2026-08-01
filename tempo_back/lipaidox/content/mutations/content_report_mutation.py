import strawberry
from django.db import transaction
from django.utils import timezone
from typing import Optional
from ..models.content_report import ContentReport, ReportReason, ReportStatus, ReportResolution, ContentModerationLog
from ..models.content import Content
from ..schema.content_report_schema import (
    ContentReportType, SubmitReportInput, ReviewReportInput, 
    EscalateReportInput, CreateModerationLogInput, ContentModerationLogType
)
from lipaidox.auth.permissions import UserRoles

@strawberry.type
class ContentReportMutation:
    @strawberry.mutation
    def submit_report(self, info: strawberry.types.Info, input: SubmitReportInput) -> ContentReportType:
        """Submit a content report with reason and description"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Validate reason
        valid_reasons = [r.value for r in ReportReason]
        if input.reason not in valid_reasons:
            raise Exception(f"Invalid reason. Valid reasons: {', '.join(valid_reasons)}")
        
        # Get the content
        try:
            content = Content.objects.get(id=input.contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        # Check if user already reported this content
        existing_report = ContentReport.objects.filter(
            reported_by=user,
            content=content
        ).first()
        
        if existing_report:
            raise Exception("You have already reported this content")
        
        # Get creator if content has one
        creator = getattr(content, 'creator', None)
        
        # Create the report
        with transaction.atomic():
            report = ContentReport.objects.create(
                reported_by=user,
                content=content,
                creator=creator,
                tenant=user.tenant,
                reason=input.reason,
                description=input.description,
                evidence_urls=input.evidenceUrls or [],
                status=ReportStatus.PENDING
            )
        
        return ContentReportType.from_model(report)
    
    @strawberry.mutation
    def review_report(self, info: strawberry.types.Info, input: ReviewReportInput) -> ContentReportType:
        """Review and resolve a content report (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is admin
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        # Validate resolution
        valid_resolutions = [r.value for r in ReportResolution]
        if input.resolution not in valid_resolutions:
            raise Exception(f"Invalid resolution. Valid resolutions: {', '.join(valid_resolutions)}")
        
        # Get the report
        try:
            report = ContentReport.objects.get(id=input.reportId)
        except ContentReport.DoesNotExist:
            raise Exception("Report not found")
        
        # Get admin account
        admin_account = getattr(user, 'admin_account', None)
        
        # Update the report
        with transaction.atomic():
            report.status = ReportStatus.RESOLVED
            report.reviewed_by = admin_account
            report.reviewed_at = timezone.now()
            report.resolution = input.resolution
            report.resolution_note = input.resolutionNote
            report.save()
            
            # Create moderation log
            action_description = f"Report resolved: {input.resolution}"
            ContentModerationLog.objects.create(
                content=report.content,
                moderator=admin_account,
                tenant=report.tenant,
                action=action_description,
                reason=input.resolutionNote or f"Report reviewed and resolved with: {input.resolution}",
                related_report=report
            )
        
        return ContentReportType.from_model(report)
    
    @strawberry.mutation
    def escalate_report(self, info: strawberry.types.Info, input: EscalateReportInput) -> ContentReportType:
        """Escalate a report to higher authority (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            report = ContentReport.objects.get(id=input.reportId)
        except ContentReport.DoesNotExist:
            raise Exception("Report not found")
        
        admin_account = getattr(user, 'admin_account', None)
        
        with transaction.atomic():
            report.status = ReportStatus.ESCALATED
            report.escalated_by = admin_account
            report.escalated_at = timezone.now()
            report.escalation_reason = input.escalationReason
            report.save()
        
        return ContentReportType.from_model(report)
    
    @strawberry.mutation
    def dismiss_report(self, info: strawberry.types.Info, reportId: strawberry.ID, note: Optional[str] = None) -> ContentReportType:
        """Dismiss a report without action (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            report = ContentReport.objects.get(id=reportId)
        except ContentReport.DoesNotExist:
            raise Exception("Report not found")
        
        admin_account = getattr(user, 'admin_account', None)
        
        with transaction.atomic():
            report.status = ReportStatus.DISMISSED
            report.reviewed_by = admin_account
            report.reviewed_at = timezone.now()
            report.resolution = ReportResolution.NO_ACTION
            report.resolution_note = note or "Report dismissed without action"
            report.save()
        
        return ContentReportType.from_model(report)
    
    @strawberry.mutation
    def start_review(self, info: strawberry.types.Info, reportId: strawberry.ID) -> ContentReportType:
        """Mark a report as under review (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            report = ContentReport.objects.get(id=reportId)
        except ContentReport.DoesNotExist:
            raise Exception("Report not found")
        
        with transaction.atomic():
            report.status = ReportStatus.UNDER_REVIEW
            report.save()
        
        return ContentReportType.from_model(report)
    
    @strawberry.mutation
    def create_moderation_log(self, info: strawberry.types.Info, input: CreateModerationLogInput) -> ContentModerationLogType:
        """Create a moderation log entry (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            content = Content.objects.get(id=input.contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        admin_account = getattr(user, 'admin_account', None)
        
        related_report = None
        if input.relatedReportId:
            try:
                related_report = ContentReport.objects.get(id=input.relatedReportId)
            except ContentReport.DoesNotExist:
                pass
        
        with transaction.atomic():
            log = ContentModerationLog.objects.create(
                content=content,
                moderator=admin_account,
                tenant=user.tenant,
                action=input.action,
                reason=input.reason,
                related_report=related_report
            )
        
        return ContentModerationLogType.from_model(log)
