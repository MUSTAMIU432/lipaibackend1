import strawberry
from typing import Optional, List
from ..models.content_report import ContentReport, ReportStatus, ContentModerationLog
from ..schema.content_report_schema import (
    ContentReportType, ContentModerationLogType,
    ReportStatisticsType, ReportCountByReason
)
from django.db.models import Count

@strawberry.type
class ContentReportQuery:
    @strawberry.field
    def my_reports(self, info: strawberry.types.Info) -> List[ContentReportType]:
        """Get all reports submitted by the current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        reports = ContentReport.objects.filter(
            reported_by=user
        ).order_by('-created_at')
        
        return [ContentReportType.from_model(r) for r in reports]
    
    @strawberry.field
    def content_reports(self, info: strawberry.types.Info, contentId: strawberry.ID) -> List[ContentReportType]:
        """Get all reports for a specific content (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        # Only admins can see all reports for content
        if user.role != 'admin':
            return []
        
        reports = ContentReport.objects.filter(
            content_id=contentId
        ).order_by('-created_at')
        
        return [ContentReportType.from_model(r) for r in reports]
    
    @strawberry.field
    def pending_reports(self, info: strawberry.types.Info) -> List[ContentReportType]:
        """Get all pending reports (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        # Only admins can see pending reports
        if user.role != 'admin':
            return []
        
        reports = ContentReport.objects.filter(
            status__in=[ReportStatus.PENDING, ReportStatus.UNDER_REVIEW]
        ).order_by('-created_at')
        
        return [ContentReportType.from_model(r) for r in reports]
    
    @strawberry.field
    def report_by_id(self, info: strawberry.types.Info, reportId: strawberry.ID) -> Optional[ContentReportType]:
        """Get a specific report by ID"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            report = ContentReport.objects.get(id=reportId)
            
            # Users can only see their own reports, admins can see all
            if user.role not in ['admin', 'superadmin'] and report.reported_by != user:
                return None
            
            return ContentReportType.from_model(report)
        except ContentReport.DoesNotExist:
            return None
    
    @strawberry.field
    def all_reports(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        reason: Optional[str] = None,
        limit: int = 100
    ) -> List[ContentReportType]:
        """Get all reports with optional filtering (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        if user.role not in ['admin', 'superadmin']:
            return []
        
        queryset = ContentReport.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if reason:
            queryset = queryset.filter(reason=reason)
        
        return [ContentReportType.from_model(r) for r in queryset.order_by('-created_at')[:limit]]
    
    @strawberry.field
    def report_statistics(self, info: strawberry.types.Info) -> ReportStatisticsType:
        """Get report statistics (admin only)"""
        user = info.context.request.user
        if not user.is_authenticated or user.role not in ['admin', 'superadmin']:
            return ReportStatisticsType(
                totalReports=0,
                pendingReports=0,
                underReviewReports=0,
                resolvedReports=0,
                dismissedReports=0,
                escalatedReports=0,
                reportsByReason=[]
            )
        
        total = ContentReport.objects.count()
        pending = ContentReport.objects.filter(status=ReportStatus.PENDING).count()
        under_review = ContentReport.objects.filter(status=ReportStatus.UNDER_REVIEW).count()
        resolved = ContentReport.objects.filter(status=ReportStatus.RESOLVED).count()
        dismissed = ContentReport.objects.filter(status=ReportStatus.DISMISSED).count()
        escalated = ContentReport.objects.filter(status=ReportStatus.ESCALATED).count()
        
        reason_counts = ContentReport.objects.values('reason').annotate(count=Count('id'))
        reports_by_reason = [ReportCountByReason(reason=r['reason'], count=r['count']) for r in reason_counts]
        
        return ReportStatisticsType(
            totalReports=total,
            pendingReports=pending,
            underReviewReports=under_review,
            resolvedReports=resolved,
            dismissedReports=dismissed,
            escalatedReports=escalated,
            reportsByReason=reports_by_reason
        )
