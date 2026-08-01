import strawberry
from django.db import transaction
from django.utils import timezone
from typing import Optional, List
from ..models import (
    AdminAccount,
    Announcement, AnnouncementRead, AnnouncementType, AnnouncementTarget, AnnouncementStatus,
    PlatformPost, PlatformPostType,
    PlatformAccount,
    AdminAction, AdminActionCategory, AdminActionType
)
from ..schema.admin_schema import (
    AnnouncementType as AnnouncementGQLType,
    PlatformPostType as PlatformPostGQLType,
    AnnouncementReadType,
    CreateAnnouncementInput, UpdateAnnouncementInput,
    CreatePlatformPostInput, MarkAnnouncementReadInput
)
from lipaidox.auth.permissions import UserRoles

def require_admin(user):
    """Check if user is an admin"""
    if not user.is_authenticated:
        raise Exception("Authentication required")
    if user.role not in [UserRoles.ADMIN, 'superadmin']:
        raise Exception("Admin access required")
    return True

@strawberry.type
class AnnouncementMutation:
    @strawberry.mutation
    def create_announcement(self, info: strawberry.types.Info, input: CreateAnnouncementInput) -> AnnouncementGQLType:
        """Create a new announcement"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        # Validate types
        valid_types = [t.value for t in AnnouncementType]
        if input.announcementType not in valid_types:
            raise Exception(f"Invalid type. Valid: {', '.join(valid_types)}")
        
        valid_targets = [t.value for t in AnnouncementTarget]
        if input.targetAudience not in valid_targets:
            raise Exception(f"Invalid target. Valid: {', '.join(valid_targets)}")
        
        try:
            platform_account = PlatformAccount.objects.get(id=input.platformAccountId)
        except PlatformAccount.DoesNotExist:
            raise Exception("Platform account not found")
        
        # Determine status based on scheduling
        status = AnnouncementStatus.DRAFT
        if input.scheduledAt:
            status = AnnouncementStatus.SCHEDULED
        
        announcement = Announcement.objects.create(
            platform_account=platform_account,
            created_by_admin=admin_account,
            tenant=user.tenant,
            title=input.title,
            body=input.body,
            announcement_type=input.announcementType,
            banner_image_url=input.bannerImageUrl,
            cta_label=input.ctaLabel,
            cta_url=input.ctaUrl,
            target_audience=input.targetAudience,
            target_user_ids=[str(uid) for uid in input.targetUserIds] if input.targetUserIds else [],
            status=status,
            is_pinned=input.isPinned,
            show_as_banner=input.showAsBanner,
            show_in_feed=input.showInFeed,
            show_as_notification=input.showAsNotification,
            scheduled_at=input.scheduledAt,
            expires_at=input.expiresAt,
        )
        
        # Record admin action
        AdminAction.objects.create(
            admin=admin_account,
            tenant=user.tenant,
            category=AdminActionCategory.ANNOUNCEMENT,
            action_type=AdminActionType.ANNOUNCEMENT_CREATED,
            reason=f"Created announcement: {input.title}",
        )
        
        return AnnouncementGQLType.from_model(announcement)

    @strawberry.mutation
    def update_announcement(self, info: strawberry.types.Info, announcementId: strawberry.ID, input: UpdateAnnouncementInput) -> AnnouncementGQLType:
        """Update an announcement"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        try:
            announcement = Announcement.objects.get(id=announcementId)
        except Announcement.DoesNotExist:
            raise Exception("Announcement not found")
        
        if input.title is not None:
            announcement.title = input.title
        if input.body is not None:
            announcement.body = input.body
        if input.bannerImageUrl is not None:
            announcement.banner_image_url = input.bannerImageUrl
        if input.ctaLabel is not None:
            announcement.cta_label = input.ctaLabel
        if input.ctaUrl is not None:
            announcement.cta_url = input.ctaUrl
        if input.status is not None:
            announcement.status = input.status
            if input.status == 'published':
                announcement.published_at = timezone.now()
        if input.isPinned is not None:
            announcement.is_pinned = input.isPinned
        if input.showAsBanner is not None:
            announcement.show_as_banner = input.showAsBanner
        if input.showInFeed is not None:
            announcement.show_in_feed = input.showInFeed
        if input.showAsNotification is not None:
            announcement.show_as_notification = input.showAsNotification
        
        announcement.save()
        
        # Record admin action
        AdminAction.objects.create(
            admin=admin_account,
            tenant=user.tenant,
            category=AdminActionCategory.ANNOUNCEMENT,
            action_type=AdminActionType.ANNOUNCEMENT_UPDATED,
            reason=f"Updated announcement: {announcement.title}",
        )
        
        return AnnouncementGQLType.from_model(announcement)

    @strawberry.mutation
    def delete_announcement(self, info: strawberry.types.Info, announcementId: strawberry.ID) -> bool:
        """Delete an announcement"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        try:
            announcement = Announcement.objects.get(id=announcementId)
            title = announcement.title
            announcement.delete()
            
            # Record admin action
            AdminAction.objects.create(
                admin=admin_account,
                tenant=user.tenant,
                category=AdminActionCategory.ANNOUNCEMENT,
                action_type=AdminActionType.ANNOUNCEMENT_DELETED,
                reason=f"Deleted announcement: {title}",
            )
            
            return True
        except Announcement.DoesNotExist:
            raise Exception("Announcement not found")

    @strawberry.mutation
    def mark_announcement_read(self, info: strawberry.types.Info, input: MarkAnnouncementReadInput) -> AnnouncementReadType:
        """Mark an announcement as read or dismissed"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            announcement = Announcement.objects.get(id=input.announcementId)
        except Announcement.DoesNotExist:
            raise Exception("Announcement not found")
        
        # Check if user can see this announcement
        if announcement.target_audience == 'specific_users':
            if str(user.id) not in announcement.target_user_ids:
                raise Exception("You cannot access this announcement")
        
        read_record, created = AnnouncementRead.objects.get_or_create(
            announcement=announcement,
            user=user,
            defaults={
                'tenant': user.tenant,
                'is_dismissed': input.isDismissed,
                'dismissed_at': timezone.now() if input.isDismissed else None,
            }
        )
        
        if not created:
            read_record.is_dismissed = input.isDismissed
            if input.isDismissed:
                read_record.dismissed_at = timezone.now()
            read_record.save()
        
        # Update counts
        if input.isDismissed:
            announcement.dismissed_count += 1
        else:
            announcement.read_count += 1
        announcement.save()
        
        return AnnouncementReadType.from_model(read_record)


@strawberry.type
class PlatformPostMutation:
    @strawberry.mutation
    def create_platform_post(self, info: strawberry.types.Info, input: CreatePlatformPostInput) -> PlatformPostGQLType:
        """Create a new platform post"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        valid_types = [t.value for t in PlatformPostType]
        if input.postType not in valid_types:
            raise Exception(f"Invalid post type. Valid: {', '.join(valid_types)}")
        
        try:
            platform_account = PlatformAccount.objects.get(id=input.platformAccountId)
        except PlatformAccount.DoesNotExist:
            raise Exception("Platform account not found")
        
        from lipaidox.content.models import Content
        try:
            content = Content.objects.get(id=input.contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        platform_post = PlatformPost.objects.create(
            content=content,
            platform_account=platform_account,
            created_by_admin=admin_account,
            tenant=user.tenant,
            post_type=input.postType,
            target_audience=input.targetAudience,
            is_pinned=input.isPinned,
            allow_comments=input.allowComments,
            allow_likes=input.allowLikes,
            scheduled_at=input.scheduledAt,
            expires_at=input.expiresAt,
        )
        
        # Record admin action
        AdminAction.objects.create(
            admin=admin_account,
            tenant=user.tenant,
            category=AdminActionCategory.ANNOUNCEMENT,
            action_type=AdminActionType.PLATFORM_POST_CREATED,
            reason=f"Created platform post: {content.title}",
        )
        
        return PlatformPostGQLType.from_model(platform_post)

    @strawberry.mutation
    def remove_platform_post(self, info: strawberry.types.Info, postId: strawberry.ID) -> bool:
        """Remove a platform post"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        try:
            post = PlatformPost.objects.get(id=postId)
            title = post.content.title
            post.delete()
            
            # Record admin action
            AdminAction.objects.create(
                admin=admin_account,
                tenant=user.tenant,
                category=AdminActionCategory.ANNOUNCEMENT,
                action_type=AdminActionType.PLATFORM_POST_REMOVED,
                reason=f"Removed platform post: {title}",
            )
            
            return True
        except PlatformPost.DoesNotExist:
            raise Exception("Platform post not found")
