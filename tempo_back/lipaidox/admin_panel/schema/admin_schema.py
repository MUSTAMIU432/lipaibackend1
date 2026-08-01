import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import (
    AdminAccount, AdminAction, AdminRole, AdminActionCategory, AdminActionType,
    AccountFlag, FlagReason, FlagSeverity, FlagStatus, FlagResolution,
    PlatformAccount, PlatformAccountType,
    Announcement, AnnouncementRead, AnnouncementType, AnnouncementTarget, AnnouncementStatus,
    PlatformPost, PlatformPostType
)

# Admin Account Types
@strawberry.type
class AdminAccountType:
    id: strawberry.ID
    userId: strawberry.ID
    adminRole: str
    displayName: Optional[str]
    department: Optional[str]
    isActive: bool
    canManageKyc: bool
    canManageFinancials: bool
    canManageContent: bool
    canManageUsers: bool
    canPostAnnouncements: bool
    canGiftCredits: bool
    lastActiveAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: AdminAccount):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            adminRole=instance.admin_role,
            displayName=instance.display_name,
            department=instance.department,
            isActive=instance.is_active,
            canManageKyc=instance.can_manage_kyc,
            canManageFinancials=instance.can_manage_financials,
            canManageContent=instance.can_manage_content,
            canManageUsers=instance.can_manage_users,
            canPostAnnouncements=instance.can_post_announcements,
            canGiftCredits=instance.can_gift_credits,
            lastActiveAt=instance.last_active_at,
            createdAt=instance.created_at,
        )

@strawberry.type
class AdminActionType:
    id: strawberry.ID
    adminId: strawberry.ID
    adminName: str
    actedOnUserId: Optional[strawberry.ID]
    actedOnContentId: Optional[strawberry.ID]
    actedOnEntityId: Optional[strawberry.ID]
    actedOnEntityType: Optional[str]
    category: str
    actionType: str
    reason: Optional[str]
    notes: Optional[str]
    isReversible: bool
    reversedAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: AdminAction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            adminId=strawberry.ID(str(instance.admin_id)),
            adminName=instance.admin.display_name or instance.admin.user.username,
            actedOnUserId=strawberry.ID(str(instance.acted_on_user_id)) if instance.acted_on_user else None,
            actedOnContentId=strawberry.ID(str(instance.acted_on_content_id)) if instance.acted_on_content else None,
            actedOnEntityId=strawberry.ID(str(instance.acted_on_entity_id)) if instance.acted_on_entity_id else None,
            actedOnEntityType=instance.acted_on_entity_type,
            category=instance.category,
            actionType=instance.action_type,
            reason=instance.reason,
            notes=instance.notes,
            isReversible=instance.is_reversible,
            reversedAt=instance.reversed_at,
            createdAt=instance.created_at,
        )

# Account Flag Types
@strawberry.type
class AccountFlagType:
    id: strawberry.ID
    flaggedUserId: strawberry.ID
    flaggedUserName: str
    reason: str
    severity: str
    description: Optional[str]
    flaggedByAdminId: Optional[strawberry.ID]
    flaggedBySystem: bool
    systemTrigger: Optional[str]
    status: str
    assignedToId: Optional[strawberry.ID]
    assignedToName: Optional[str]
    resolvedById: Optional[strawberry.ID]
    resolution: Optional[str]
    resolutionNote: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: AccountFlag):
        return cls(
            id=strawberry.ID(str(instance.id)),
            flaggedUserId=strawberry.ID(str(instance.flagged_user_id)),
            flaggedUserName=instance.flagged_user.username,
            reason=instance.reason,
            severity=instance.severity,
            description=instance.description,
            flaggedByAdminId=strawberry.ID(str(instance.flagged_by_admin_id)) if instance.flagged_by_admin else None,
            flaggedBySystem=instance.flagged_by_system,
            systemTrigger=instance.system_trigger,
            status=instance.status,
            assignedToId=strawberry.ID(str(instance.assigned_to_id)) if instance.assigned_to else None,
            assignedToName=instance.assigned_to.display_name if instance.assigned_to else None,
            resolvedById=strawberry.ID(str(instance.resolved_by_id)) if instance.resolved_by else None,
            resolution=instance.resolution,
            resolutionNote=instance.resolution_note,
            createdAt=instance.created_at,
        )

# Platform Account Types
@strawberry.type
class PlatformAccountType:
    id: strawberry.ID
    userId: strawberry.ID
    accountType: str
    handle: str
    displayName: str
    bio: Optional[str]
    avatarUrl: Optional[str]
    coverUrl: Optional[str]
    isActive: bool
    isVerified: bool
    followerCount: int
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: PlatformAccount):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            accountType=instance.account_type,
            handle=instance.handle,
            displayName=instance.display_name,
            bio=instance.bio,
            avatarUrl=instance.avatar_url,
            coverUrl=instance.cover_url,
            isActive=instance.is_active,
            isVerified=instance.is_verified,
            followerCount=instance.follower_count,
            createdAt=instance.created_at,
        )

# Announcement Types
@strawberry.type
class AnnouncementType:
    id: strawberry.ID
    platformAccountId: strawberry.ID
    platformAccountHandle: str
    createdByAdminId: strawberry.ID
    title: str
    body: str
    announcementType: str
    bannerImageUrl: Optional[str]
    ctaLabel: Optional[str]
    ctaUrl: Optional[str]
    targetAudience: str
    status: str
    isPinned: bool
    showAsBanner: bool
    showInFeed: bool
    showAsNotification: bool
    scheduledAt: Optional[datetime]
    publishedAt: Optional[datetime]
    expiresAt: Optional[datetime]
    readCount: int
    dismissedCount: int
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: Announcement):
        return cls(
            id=strawberry.ID(str(instance.id)),
            platformAccountId=strawberry.ID(str(instance.platform_account_id)),
            platformAccountHandle=instance.platform_account.handle,
            createdByAdminId=strawberry.ID(str(instance.created_by_admin_id)),
            title=instance.title,
            body=instance.body,
            announcementType=instance.announcement_type,
            bannerImageUrl=instance.banner_image_url,
            ctaLabel=instance.cta_label,
            ctaUrl=instance.cta_url,
            targetAudience=instance.target_audience,
            status=instance.status,
            isPinned=instance.is_pinned,
            showAsBanner=instance.show_as_banner,
            showInFeed=instance.show_in_feed,
            showAsNotification=instance.show_as_notification,
            scheduledAt=instance.scheduled_at,
            publishedAt=instance.published_at,
            expiresAt=instance.expires_at,
            readCount=instance.read_count,
            dismissedCount=instance.dismissed_count,
            createdAt=instance.created_at,
        )

@strawberry.type
class AnnouncementReadType:
    id: strawberry.ID
    announcementId: strawberry.ID
    userId: strawberry.ID
    isDismissed: bool
    readAt: datetime
    dismissedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: AnnouncementRead):
        return cls(
            id=strawberry.ID(str(instance.id)),
            announcementId=strawberry.ID(str(instance.announcement_id)),
            userId=strawberry.ID(str(instance.user_id)),
            isDismissed=instance.is_dismissed,
            readAt=instance.read_at,
            dismissedAt=instance.dismissed_at,
        )

# Platform Post Types
@strawberry.type
class PlatformPostType:
    id: strawberry.ID
    contentId: strawberry.ID
    platformAccountId: strawberry.ID
    platformAccountHandle: str
    announcementId: Optional[strawberry.ID]
    postType: str
    targetAudience: str
    isPinned: bool
    isSystemPost: bool
    allowComments: bool
    allowLikes: bool
    scheduledAt: Optional[datetime]
    expiresAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: PlatformPost):
        return cls(
            id=strawberry.ID(str(instance.id)),
            contentId=strawberry.ID(str(instance.content_id)),
            platformAccountId=strawberry.ID(str(instance.platform_account_id)),
            platformAccountHandle=instance.platform_account.handle,
            announcementId=strawberry.ID(str(instance.announcement_id)) if instance.announcement else None,
            postType=instance.post_type,
            targetAudience=instance.target_audience,
            isPinned=instance.is_pinned,
            isSystemPost=instance.is_system_post,
            allowComments=instance.allow_comments,
            allowLikes=instance.allow_likes,
            scheduledAt=instance.scheduled_at,
            expiresAt=instance.expires_at,
            createdAt=instance.created_at,
        )

# Input Types
@strawberry.input
class CreateAdminAccountInput:
    userId: strawberry.ID
    adminRole: str
    displayName: Optional[str] = None
    department: Optional[str] = None
    canManageKyc: bool = False
    canManageFinancials: bool = False
    canManageContent: bool = False
    canManageUsers: bool = False
    canPostAnnouncements: bool = False
    canGiftCredits: bool = False

@strawberry.input
class UpdateAdminAccountInput:
    adminRole: Optional[str] = None
    displayName: Optional[str] = None
    department: Optional[str] = None
    isActive: Optional[bool] = None
    canManageKyc: Optional[bool] = None
    canManageFinancials: Optional[bool] = None
    canManageContent: Optional[bool] = None
    canManageUsers: Optional[bool] = None
    canPostAnnouncements: Optional[bool] = None
    canGiftCredits: Optional[bool] = None

@strawberry.input
class RecordAdminActionInput:
    actedOnUserId: Optional[strawberry.ID] = None
    actedOnContentId: Optional[strawberry.ID] = None
    actedOnEntityId: Optional[strawberry.ID] = None
    actedOnEntityType: Optional[str] = None
    category: str
    actionType: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    isReversible: bool = False

@strawberry.input
class CreateAccountFlagInput:
    flaggedUserId: strawberry.ID
    reason: str
    severity: str
    description: Optional[str] = None
    evidence: Optional[List[str]] = None

@strawberry.input
class UpdateAccountFlagInput:
    severity: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignedToId: Optional[strawberry.ID] = None
    investigationNotes: Optional[str] = None
    resolution: Optional[str] = None
    resolutionNote: Optional[str] = None

@strawberry.input
class CreatePlatformAccountInput:
    userId: strawberry.ID
    accountType: str
    handle: str
    displayName: str
    bio: Optional[str] = None
    avatarUrl: Optional[str] = None
    coverUrl: Optional[str] = None

@strawberry.input
class UpdatePlatformAccountInput:
    accountType: Optional[str] = None
    displayName: Optional[str] = None
    bio: Optional[str] = None
    avatarUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    isActive: Optional[bool] = None

@strawberry.input
class CreateAnnouncementInput:
    platformAccountId: strawberry.ID
    title: str
    body: str
    announcementType: Optional[str] = 'general'
    bannerImageUrl: Optional[str] = None
    ctaLabel: Optional[str] = None
    ctaUrl: Optional[str] = None
    targetAudience: Optional[str] = 'all_users'
    targetUserIds: Optional[List[strawberry.ID]] = None
    isPinned: bool = False
    showAsBanner: bool = False
    showInFeed: bool = True
    showAsNotification: bool = True
    scheduledAt: Optional[datetime] = None
    expiresAt: Optional[datetime] = None

@strawberry.input
class UpdateAnnouncementInput:
    title: Optional[str] = None
    body: Optional[str] = None
    bannerImageUrl: Optional[str] = None
    ctaLabel: Optional[str] = None
    ctaUrl: Optional[str] = None
    status: Optional[str] = None
    isPinned: Optional[bool] = None
    showAsBanner: Optional[bool] = None
    showInFeed: Optional[bool] = None
    showAsNotification: Optional[bool] = None

@strawberry.input
class CreatePlatformPostInput:
    contentId: strawberry.ID
    platformAccountId: strawberry.ID
    postType: Optional[str] = 'announcement'
    targetAudience: Optional[str] = 'all_users'
    isPinned: bool = False
    allowComments: bool = False
    allowLikes: bool = True
    scheduledAt: Optional[datetime] = None
    expiresAt: Optional[datetime] = None

@strawberry.input
class MarkAnnouncementReadInput:
    announcementId: strawberry.ID
    isDismissed: bool = False
