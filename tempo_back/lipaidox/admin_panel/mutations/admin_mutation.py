import strawberry
from django.db import transaction
from django.utils import timezone
from typing import Optional, List
from ..models import (
    AdminAccount, AdminAction, AdminRole, AdminActionCategory, AdminActionType,
    AccountFlag, FlagReason, FlagSeverity, FlagStatus, FlagResolution,
    PlatformAccount, PlatformAccountType,
    Announcement, AnnouncementRead, AnnouncementType, AnnouncementTarget, AnnouncementStatus,
    PlatformPost, PlatformPostType
)
from ..schema.admin_schema import (
    AdminAccountType, AdminActionType, AccountFlagType,
    CreateAdminAccountInput, UpdateAdminAccountInput, RecordAdminActionInput,
    CreateAccountFlagInput, UpdateAccountFlagInput,
    CreatePlatformAccountInput, UpdatePlatformAccountInput,
    CreateAnnouncementInput, UpdateAnnouncementInput,
    CreatePlatformPostInput, MarkAnnouncementReadInput,
    PlatformAccountType as PlatformAccountGQLType,
    AnnouncementType as AnnouncementGQLType,
    PlatformPostType as PlatformPostGQLType,
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
class AdminPanelMutation:
    # Admin Account Mutations
    @strawberry.mutation
    def create_admin_account(self, info: strawberry.types.Info, input: CreateAdminAccountInput) -> AdminAccountType:
        """Create a new admin account (superadmin only)"""
        user = info.context.request.user
        require_admin(user)
        
        # Check if user is superadmin
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or admin_account.admin_role != AdminRole.SUPERADMIN:
            raise Exception("Superadmin access required")
        
        # Validate role
        valid_roles = [r.value for r in AdminRole]
        if input.adminRole not in valid_roles:
            raise Exception(f"Invalid role. Valid roles: {', '.join(valid_roles)}")
        
        from lipaidox.auth.models import User
        try:
            target_user = User.objects.get(id=input.userId)
        except User.DoesNotExist:
            raise Exception("User not found")
        
        # Check if admin account already exists
        if hasattr(target_user, 'admin_account'):
            raise Exception("User already has an admin account")
        
        with transaction.atomic():
            admin = AdminAccount.objects.create(
                user=target_user,
                tenant=user.tenant,
                admin_role=input.adminRole,
                display_name=input.displayName,
                department=input.department,
                can_manage_kyc=input.canManageKyc,
                can_manage_financials=input.canManageFinancials,
                can_manage_content=input.canManageContent,
                can_manage_users=input.canManageUsers,
                can_post_announcements=input.canPostAnnouncements,
                can_gift_credits=input.canGiftCredits,
            )
            
            # Record the action
            AdminAction.objects.create(
                admin=admin_account,
                acted_on_user=target_user,
                tenant=user.tenant,
                category=AdminActionCategory.USER_MANAGEMENT,
                action_type=AdminActionType.USER_ROLE_CHANGED,
                reason=f"Created admin account with role: {input.adminRole}",
                notes=f"Admin account created by {user.username}",
            )
        
        return AdminAccountType.from_model(admin)

    @strawberry.mutation
    def update_admin_account(self, info: strawberry.types.Info, adminId: strawberry.ID, input: UpdateAdminAccountInput) -> AdminAccountType:
        """Update an admin account (superadmin only)"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or admin_account.admin_role != AdminRole.SUPERADMIN:
            raise Exception("Superadmin access required")
        
        try:
            target_admin = AdminAccount.objects.get(id=adminId)
        except AdminAccount.DoesNotExist:
            raise Exception("Admin account not found")
        
        # Update fields
        if input.adminRole is not None:
            target_admin.admin_role = input.adminRole
        if input.displayName is not None:
            target_admin.display_name = input.displayName
        if input.department is not None:
            target_admin.department = input.department
        if input.isActive is not None:
            target_admin.is_active = input.isActive
        if input.canManageKyc is not None:
            target_admin.can_manage_kyc = input.canManageKyc
        if input.canManageFinancials is not None:
            target_admin.can_manage_financials = input.canManageFinancials
        if input.canManageContent is not None:
            target_admin.can_manage_content = input.canManageContent
        if input.canManageUsers is not None:
            target_admin.can_manage_users = input.canManageUsers
        if input.canPostAnnouncements is not None:
            target_admin.can_post_announcements = input.canPostAnnouncements
        if input.canGiftCredits is not None:
            target_admin.can_gift_credits = input.canGiftCredits
        
        target_admin.save()
        return AdminAccountType.from_model(target_admin)

    # Admin Action Recording
    @strawberry.mutation
    def record_admin_action(self, info: strawberry.types.Info, input: RecordAdminActionInput) -> AdminActionType:
        """Record an admin action for audit trail"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account:
            raise Exception("Admin account not found")
        
        # Validate category and action type
        valid_categories = [c.value for c in AdminActionCategory]
        if input.category not in valid_categories:
            raise Exception(f"Invalid category. Valid: {', '.join(valid_categories)}")
        
        valid_actions = [a.value for a in AdminActionType]
        if input.actionType not in valid_actions:
            raise Exception(f"Invalid action type. Valid: {', '.join(valid_actions)}")
        
        from lipaidox.auth.models import User
        from lipaidox.content.models import Content
        
        acted_on_user = None
        acted_on_content = None
        
        if input.actedOnUserId:
            try:
                acted_on_user = User.objects.get(id=input.actedOnUserId)
            except User.DoesNotExist:
                pass
        
        if input.actedOnContentId:
            try:
                acted_on_content = Content.objects.get(id=input.actedOnContentId)
            except Content.DoesNotExist:
                pass
        
        action = AdminAction.objects.create(
            admin=admin_account,
            acted_on_user=acted_on_user,
            acted_on_content=acted_on_content,
            acted_on_entity_id=input.actedOnEntityId,
            acted_on_entity_type=input.actedOnEntityType,
            tenant=user.tenant,
            category=input.category,
            action_type=input.actionType,
            reason=input.reason,
            notes=input.notes,
            is_reversible=input.isReversible,
            ip_address=info.context.request.META.get('REMOTE_ADDR'),
            user_agent=info.context.request.META.get('HTTP_USER_AGENT'),
        )
        
        return AdminActionType.from_model(action)

    # Account Flag Mutations
    @strawberry.mutation
    def create_account_flag(self, info: strawberry.types.Info, input: CreateAccountFlagInput) -> AccountFlagType:
        """Create a new account flag"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_manage_users:
            raise Exception("Permission denied: can_manage_users required")
        
        # Validate reason and severity
        valid_reasons = [r.value for r in FlagReason]
        if input.reason not in valid_reasons:
            raise Exception(f"Invalid reason. Valid: {', '.join(valid_reasons)}")
        
        valid_severities = [s.value for s in FlagSeverity]
        if input.severity not in valid_severities:
            raise Exception(f"Invalid severity. Valid: {', '.join(valid_severities)}")
        
        from lipaidox.auth.models import User
        try:
            flagged_user = User.objects.get(id=input.flaggedUserId)
        except User.DoesNotExist:
            raise Exception("User not found")
        
        with transaction.atomic():
            flag = AccountFlag.objects.create(
                flagged_user=flagged_user,
                tenant=user.tenant,
                reason=input.reason,
                severity=input.severity,
                description=input.description,
                evidence={"urls": input.evidence} if input.evidence else {},
                flagged_by_admin=admin_account,
                status=FlagStatus.OPEN,
            )
            
            # Record admin action
            AdminAction.objects.create(
                admin=admin_account,
                acted_on_user=flagged_user,
                tenant=user.tenant,
                category=AdminActionCategory.ACCOUNT_FLAG,
                action_type=AdminActionType.ACCOUNT_FLAGGED,
                reason=input.reason,
                notes=input.description,
            )
        
        return AccountFlagType.from_model(flag)

    @strawberry.mutation
    def update_account_flag(self, info: strawberry.types.Info, flagId: strawberry.ID, input: UpdateAccountFlagInput) -> AccountFlagType:
        """Update an account flag"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_manage_users:
            raise Exception("Permission denied: can_manage_users required")
        
        try:
            flag = AccountFlag.objects.get(id=flagId)
        except AccountFlag.DoesNotExist:
            raise Exception("Flag not found")
        
        # Update fields
        if input.severity is not None:
            flag.severity = input.severity
        if input.description is not None:
            flag.description = input.description
        if input.status is not None:
            flag.status = input.status
        if input.investigationNotes is not None:
            flag.investigation_notes = input.investigationNotes
        
        if input.assignedToId is not None:
            try:
                assigned_admin = AdminAccount.objects.get(id=input.assignedToId)
                flag.assigned_to = assigned_admin
                flag.assigned_at = timezone.now()
            except AdminAccount.DoesNotExist:
                raise Exception("Assigned admin not found")
        
        if input.resolution is not None:
            flag.resolution = input.resolution
            flag.resolved_by = admin_account
            flag.resolved_at = timezone.now()
            flag.status = FlagStatus.RESOLVED
            
            # Record admin action
            AdminAction.objects.create(
                admin=admin_account,
                acted_on_user=flag.flagged_user,
                tenant=user.tenant,
                category=AdminActionCategory.ACCOUNT_FLAG,
                action_type=AdminActionType.ACCOUNT_FLAG_RESOLVED,
                reason=input.resolution,
                notes=input.resolutionNote,
            )
        
        flag.save()
        return AccountFlagType.from_model(flag)

    # Platform Account Mutations
    @strawberry.mutation
    def create_platform_account(self, info: strawberry.types.Info, input: CreatePlatformAccountInput) -> PlatformAccountGQLType:
        """Create a new platform account (admin with can_post_announcements)"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        valid_types = [t.value for t in PlatformAccountType]
        if input.accountType not in valid_types:
            raise Exception(f"Invalid account type. Valid: {', '.join(valid_types)}")
        
        from lipaidox.auth.models import User
        try:
            target_user = User.objects.get(id=input.userId)
        except User.DoesNotExist:
            raise Exception("User not found")
        
        # Check if handle is unique
        if PlatformAccount.objects.filter(handle=input.handle).exists():
            raise Exception("Handle already taken")
        
        platform_account = PlatformAccount.objects.create(
            user=target_user,
            tenant=user.tenant,
            account_type=input.accountType,
            handle=input.handle,
            display_name=input.displayName,
            bio=input.bio,
            avatar_url=input.avatarUrl,
            cover_url=input.coverUrl,
            managed_by=admin_account,
        )
        
        return PlatformAccountGQLType.from_model(platform_account)

    @strawberry.mutation
    def update_platform_account(self, info: strawberry.types.Info, accountId: strawberry.ID, input: UpdatePlatformAccountInput) -> PlatformAccountGQLType:
        """Update a platform account"""
        user = info.context.request.user
        require_admin(user)
        
        admin_account = getattr(user, 'admin_account', None)
        if not admin_account or not admin_account.can_post_announcements:
            raise Exception("Permission denied: can_post_announcements required")
        
        try:
            platform_account = PlatformAccount.objects.get(id=accountId)
        except PlatformAccount.DoesNotExist:
            raise Exception("Platform account not found")
        
        if input.accountType is not None:
            platform_account.account_type = input.accountType
        if input.displayName is not None:
            platform_account.display_name = input.displayName
        if input.bio is not None:
            platform_account.bio = input.bio
        if input.avatarUrl is not None:
            platform_account.avatar_url = input.avatarUrl
        if input.coverUrl is not None:
            platform_account.cover_url = input.coverUrl
        if input.isActive is not None:
            platform_account.is_active = input.isActive
        
        platform_account.save()
        return PlatformAccountGQLType.from_model(platform_account)
