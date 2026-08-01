import strawberry
from typing import Optional, List
from ..models import (
    AdminAccount, AdminAction,
    AccountFlag, FlagStatus,
    PlatformAccount,
    Announcement, AnnouncementRead, AnnouncementStatus,
    PlatformPost
)
from ..schema.admin_schema import (
    AdminAccountType, AdminActionType, AccountFlagType,
    PlatformAccountType, AnnouncementType, PlatformPostType,
    AnnouncementReadType
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
class AdminPanelQuery:
    # Admin Account Queries
    @strawberry.field
    def all_admin_accounts(self, info: strawberry.types.Info) -> List[AdminAccountType]:
        """Get all admin accounts (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        admins = AdminAccount.objects.all().order_by('-created_at')
        return [AdminAccountType.from_model(a) for a in admins]

    @strawberry.field
    def admin_account_by_id(self, info: strawberry.types.Info, adminId: strawberry.ID) -> Optional[AdminAccountType]:
        """Get a specific admin account by ID"""
        user = info.context.request.user
        require_admin(user)
        
        try:
            admin = AdminAccount.objects.get(id=adminId)
            return AdminAccountType.from_model(admin)
        except AdminAccount.DoesNotExist:
            return None

    @strawberry.field
    def my_admin_account(self, info: strawberry.types.Info) -> Optional[AdminAccountType]:
        """Get the current user's admin account"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if admin_account:
            return AdminAccountType.from_model(admin_account)
        return None

    # Admin Action Queries (Audit Trail)
    @strawberry.field
    def admin_actions(
        self,
        info: strawberry.types.Info,
        adminId: Optional[strawberry.ID] = None,
        category: Optional[str] = None,
        actionType: Optional[str] = None,
        limit: int = 50
    ) -> List[AdminActionType]:
        """Get admin action audit trail (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        queryset = AdminAction.objects.all().order_by('-created_at')
        
        if adminId:
            queryset = queryset.filter(admin_id=adminId)
        if category:
            queryset = queryset.filter(category=category)
        if actionType:
            queryset = queryset.filter(action_type=actionType)
        
        return [AdminActionType.from_model(a) for a in queryset[:limit]]

    @strawberry.field
    def actions_on_user(self, info: strawberry.types.Info, userId: strawberry.ID) -> List[AdminActionType]:
        """Get all admin actions taken on a specific user"""
        user = info.context.request.user
        require_admin(user)
        
        actions = AdminAction.objects.filter(
            acted_on_user_id=userId
        ).order_by('-created_at')
        
        return [AdminActionType.from_model(a) for a in actions]

    # Account Flag Queries
    @strawberry.field
    def all_account_flags(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[AccountFlagType]:
        """Get all account flags (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_manage_users:
            raise Exception("Permission denied: can_manage_users required")
        
        queryset = AccountFlag.objects.all().order_by('-created_at')
        
        if status:
            queryset = queryset.filter(status=status)
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return [AccountFlagType.from_model(f) for f in queryset]

    @strawberry.field
    def my_assigned_flags(self, info: strawberry.types.Info) -> List[AccountFlagType]:
        """Get account flags assigned to current admin"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account:
            return []
        
        flags = AccountFlag.objects.filter(
            assigned_to=admin_account,
            status__in=['open', 'under_investigation']
        ).order_by('-created_at')
        
        return [AccountFlagType.from_model(f) for f in flags]

    @strawberry.field
    def flag_by_id(self, info: strawberry.types.Info, flagId: strawberry.ID) -> Optional[AccountFlagType]:
        """Get a specific account flag by ID"""
        user = info.context.request.user
        require_admin(user)
        
        try:
            flag = AccountFlag.objects.get(id=flagId)
            return AccountFlagType.from_model(flag)
        except AccountFlag.DoesNotExist:
            return None

    @strawberry.field
    def user_flags(self, info: strawberry.types.Info, userId: strawberry.ID) -> List[AccountFlagType]:
        """Get all flags for a specific user"""
        user = info.context.request.user
        require_admin(user)
        
        flags = AccountFlag.objects.filter(
            flagged_user_id=userId
        ).order_by('-created_at')
        
        return [AccountFlagType.from_model(f) for f in flags]

    # Platform Account Queries
    @strawberry.field
    def all_platform_accounts(self, info: strawberry.types.Info, isActive: Optional[bool] = None) -> List[PlatformAccountType]:
        """Get all platform accounts (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        queryset = PlatformAccount.objects.all().order_by('-created_at')
        
        if isActive is not None:
            queryset = queryset.filter(is_active=isActive)
        
        return [PlatformAccountType.from_model(a) for a in queryset]

    @strawberry.field
    def platform_account_by_handle(self, info: strawberry.types.Info, handle: str) -> Optional[PlatformAccountType]:
        """Get a platform account by handle"""
        try:
            account = PlatformAccount.objects.get(handle=handle, is_active=True)
            return PlatformAccountType.from_model(account)
        except PlatformAccount.DoesNotExist:
            return None

    # Announcement Queries
    @strawberry.field
    def all_announcements(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        targetAudience: Optional[str] = None
    ) -> List[AnnouncementType]:
        """Get all announcements (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        queryset = Announcement.objects.all().order_by('-created_at')
        
        if status:
            queryset = queryset.filter(status=status)
        if targetAudience:
            queryset = queryset.filter(target_audience=targetAudience)
        
        return [AnnouncementType.from_model(a) for a in queryset]

    @strawberry.field
    def my_announcements(self, info: strawberry.types.Info) -> List[AnnouncementType]:
        """Get announcements visible to current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        # Get published announcements that haven't expired
        queryset = Announcement.objects.filter(
            status=AnnouncementStatus.PUBLISHED,
        ).order_by('-is_pinned', '-published_at')
        
        # Filter by target audience
        if user.role == 'creator':
            queryset = queryset.filter(
                target_audience__in=['all_users', 'creators_only']
            )
        else:
            queryset = queryset.filter(
                target_audience__in=['all_users', 'fans_only']
            )
        
        return [AnnouncementType.from_model(a) for a in queryset]

    @strawberry.field
    def announcement_by_id(self, info: strawberry.types.Info, announcementId: strawberry.ID) -> Optional[AnnouncementType]:
        """Get a specific announcement by ID"""
        user = info.context.request.user
        
        try:
            announcement = Announcement.objects.get(id=announcementId)
            
            # Check visibility
            if announcement.target_audience == 'specific_users':
                if not user.is_authenticated or str(user.id) not in announcement.target_user_ids:
                    return None
            
            return AnnouncementType.from_model(announcement)
        except Announcement.DoesNotExist:
            return None

    @strawberry.field
    def my_announcement_reads(self, info: strawberry.types.Info) -> List[AnnouncementReadType]:
        """Get current user's announcement read/dismiss status"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        reads = AnnouncementRead.objects.filter(
            user=user
        ).order_by('-read_at')
        
        return [AnnouncementReadType.from_model(r) for r in reads]

    # Platform Post Queries
    @strawberry.field
    def all_platform_posts(
        self,
        info: strawberry.types.Info,
        platformAccountId: Optional[strawberry.ID] = None,
        isPinned: Optional[bool] = None
    ) -> List[PlatformPostType]:
        """Get all platform posts (admin only)"""
        user = info.context.request.user
        require_admin(user)
        
        queryset = PlatformPost.objects.all().order_by('-is_pinned', '-created_at')
        
        if platformAccountId:
            queryset = queryset.filter(platform_account_id=platformAccountId)
        if isPinned is not None:
            queryset = queryset.filter(is_pinned=isPinned)
        
        return [PlatformPostType.from_model(p) for p in queryset]

    @strawberry.field
    def my_platform_posts(self, info: strawberry.types.Info) -> List[PlatformPostType]:
        """Get platform posts visible to current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        # Get non-expired posts
        from django.utils import timezone
        queryset = PlatformPost.objects.filter(
            expires_at__isnull=True
        ) | PlatformPost.objects.filter(
            expires_at__gt=timezone.now()
        )
        
        # Filter by target audience
        if user.role == 'creator':
            queryset = queryset.filter(
                target_audience__in=['all_users', 'creators_only']
            )
        else:
            queryset = queryset.filter(
                target_audience__in=['all_users', 'fans_only']
            )
        
        queryset = queryset.order_by('-is_pinned', '-created_at')
        
        return [PlatformPostType.from_model(p) for p in queryset]

    @strawberry.field
    def platform_posts_by_account(self, info: strawberry.types.Info, handle: str) -> List[PlatformPostType]:
        """Get platform posts by account handle"""
        try:
            account = PlatformAccount.objects.get(handle=handle, is_active=True)
            posts = PlatformPost.objects.filter(
                platform_account=account
            ).order_by('-is_pinned', '-created_at')
            
            return [PlatformPostType.from_model(p) for p in posts]
        except PlatformAccount.DoesNotExist:
            return []
