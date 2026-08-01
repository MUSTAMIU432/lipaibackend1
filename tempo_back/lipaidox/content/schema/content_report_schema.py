import strawberry
from typing import Optional, List
from datetime import datetime
from ..models.content_report import (
    ContentReport, ContentModerationLog,
    ReportReason, ReportStatus, ReportResolution
)


@strawberry.type
class ContentReportType:
    id: strawberry.ID
    contentId: strawberry.ID
    reportedById: Optional[strawberry.ID]
    creatorId: Optional[strawberry.ID]
    reason: str
    description: Optional[str]
    evidenceUrls: List[str]
    status: str
    reviewedById: Optional[strawberry.ID]
    reviewedAt: Optional[datetime]
    resolution: Optional[str]
    resolutionNote: Optional[str]
    escalatedById: Optional[strawberry.ID]
    escalatedAt: Optional[datetime]
    escalationReason: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: ContentReport):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            reportedById=strawberry.ID(str(instance.reported_by_id)) if instance.reported_by else None,
            creatorId=strawberry.ID(str(instance.creator_id)) if instance.creator else None,
            reason=instance.reason,
            description=instance.description,
            evidenceUrls=instance.evidence_urls or [],
            status=instance.status,
            reviewedById=strawberry.ID(str(instance.reviewed_by_id)) if instance.reviewed_by else None,
            reviewedAt=instance.reviewed_at,
            resolution=instance.resolution,
            resolutionNote=instance.resolution_note,
            escalatedById=strawberry.ID(str(instance.escalated_by_id)) if instance.escalated_by else None,
            escalatedAt=instance.escalated_at,
            escalationReason=instance.escalation_reason,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class ContentModerationLogType:
    id: strawberry.ID
    contentId: strawberry.ID
    moderatorId: strawberry.ID
    action: str
    reason: str
    relatedReportId: Optional[strawberry.ID]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: ContentModerationLog):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            moderatorId=strawberry.ID(str(instance.moderator_id)),
            action=instance.action,
            reason=instance.reason,
            relatedReportId=strawberry.ID(str(instance.related_report_id)) if instance.related_report else None,
            createdAt=instance.created_at,
        )


# Report Statistics
@strawberry.type
class ReportStatisticsType:
    totalReports: int
    pendingReports: int
    underReviewReports: int
    resolvedReports: int
    dismissedReports: int
    escalatedReports: int
    reportsByReason: List['ReportCountByReason']


@strawberry.type
class ReportCountByReason:
    reason: str
    count: int


# Input Types
@strawberry.input
class SubmitReportInput:
    contentId: strawberry.ID
    reason: str
    description: Optional[str] = None
    evidenceUrls: Optional[List[str]] = None


@strawberry.input
class ReviewReportInput:
    reportId: strawberry.ID
    resolution: str
    resolutionNote: Optional[str] = None


@strawberry.input
class EscalateReportInput:
    reportId: strawberry.ID
    escalationReason: str


@strawberry.input
class CreateModerationLogInput:
    contentId: strawberry.ID
    action: str
    reason: str
    relatedReportId: Optional[strawberry.ID] = None
