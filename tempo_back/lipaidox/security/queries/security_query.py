import strawberry
from typing import Optional, List
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta, date

from ..models import (
    SecuritySettings, TwoFAMethod,
    LoginHistory, LoginResult,
    DeviceSession, DeviceType, SessionStatus,
    SecurityEvent, SecurityEventType,
    TwoFAAttempt, TwoFAAttemptResult
)

from ..schema.security_schema import (
    # Types
    SecuritySettingsType, LoginHistoryType, DeviceSessionType,
    SecurityEventType as SecurityEventTypeType, TwoFAAttemptType,
    
    # Input Types
    TwoFASetupInput, TwoFAVerifyInput, SecuritySettingsUpdateInput,
    DeviceSessionFilterInput, SecurityEventFilterInput, LoginHistoryFilterInput
)

from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_admin(user):
    """Check if user is admin"""
    if user.role not in [UserRoles.ADMIN, 'superadmin']:
        raise Exception("Admin access required")
    return True


@strawberry.type
class SecurityQuery:
    # Security Settings Queries
    @strawberry.field
    def my_security_settings(self, info: strawberry.types.Info) -> SecuritySettingsType:
        """Get current user's security settings"""
        user = require_auth(info)
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        return SecuritySettingsType.from_model(settings)

    # Login History Queries
    @strawberry.field
    def my_login_history(
        self,
        info: strawberry.types.Info,
        days: int = 30,
        filter: Optional[LoginHistoryFilterInput] = None,
        limit: int = 100
    ) -> List[LoginHistoryType]:
        """Get current user's login history"""
        user = require_auth(info)
        
        queryset = LoginHistory.get_user_login_attempts(user, days=days)
        
        if filter:
            if filter.result:
                queryset = queryset.filter(result=filter.result)
            if filter.isSuspicious is not None:
                queryset = queryset.filter(is_suspicious=filter.isSuspicious)
        
        return [LoginHistoryType.from_model(item) for item in queryset[:limit]]

    @strawberry.field
    def login_statistics(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> dict:
        """Get login statistics for current user"""
        user = require_auth(info)
        
        return LoginHistory.get_login_statistics(user, days=days)

    # Device Session Queries
    @strawberry.field
    def my_device_sessions(
        self,
        info: strawberry.types.Info,
        activeOnly: bool = True,
        filter: Optional[DeviceSessionFilterInput] = None
    ) -> List[DeviceSessionType]:
        """Get current user's device sessions"""
        user = require_auth(info)
        
        queryset = DeviceSession.get_user_sessions(user, active_only=activeOnly)
        
        if filter:
            if filter.status:
                queryset = queryset.filter(status=filter.status)
            if filter.isTrusted is not None:
                queryset = queryset.filter(is_trusted=filter.isTrusted)
            if filter.deviceType:
                queryset = queryset.filter(device_type=filter.deviceType)
        
        return [DeviceSessionType.from_model(session) for session in queryset]

    @strawberry.field
    def trusted_devices(self, info: strawberry.types.Info) -> List[DeviceSessionType]:
        """Get current user's trusted devices"""
        user = require_auth(info)
        
        trusted_devices = DeviceSession.get_trusted_devices(user)
        
        return [DeviceSessionType.from_model(device) for device in trusted_devices]

    # Security Event Queries
    @strawberry.field
    def my_security_events(
        self,
        info: strawberry.types.Info,
        days: int = 30,
        eventType: Optional[str] = None,
        limit: int = 100
    ) -> List[SecurityEventTypeType]:
        """Get current user's security events"""
        user = require_auth(info)
        
        events = SecurityEvent.get_user_events(user, days=days, event_type=eventType)
        
        return [SecurityEventTypeType.from_model(event) for event in events[:limit]]

    @strawberry.field
    def security_summary(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> dict:
        """Get security summary for current user"""
        user = require_auth(info)
        
        return SecurityEvent.get_security_summary(user, days=days)

    # Two FA Queries
    @strawberry.field
    def my_two_fa_attempts(
        self,
        info: strawberry.types.Info,
        hours: int = 24,
        limit: int = 50
    ) -> List[TwoFAAttemptType]:
        """Get current user's 2FA attempts"""
        user = require_auth(info)
        
        attempts = TwoFAAttempt.get_user_attempts(user, hours=hours)
        
        return [TwoFAAttemptType.from_model(attempt) for attempt in attempts[:limit]]

    # Admin Queries
    @strawberry.field
    def platform_login_history(
        self,
        info: strawberry.types.Info,
        days: int = 30,
        result: Optional[str] = None,
        suspiciousOnly: bool = False,
        limit: int = 100
    ) -> List[LoginHistoryType]:
        """Get platform login history (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = LoginHistory.objects.filter(tenant=user.tenant)
        
        if days:
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(logged_at__gte=cutoff_date)
        
        if result:
            queryset = queryset.filter(result=result)
        
        if suspiciousOnly:
            queryset = queryset.filter(is_suspicious=True)
        
        login_history = queryset.select_related('user').order_by('-logged_at')[:limit]
        
        return [LoginHistoryType.from_model(item) for item in login_history]

    @strawberry.field
    def platform_security_events(
        self,
        info: strawberry.types.Info,
        days: int = 7,
        eventType: Optional[str] = None,
        limit: int = 100
    ) -> List[SecurityEventTypeType]:
        """Get platform security events (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        queryset = SecurityEvent.objects.filter(tenant=user.tenant)
        
        if days:
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        if eventType:
            queryset = queryset.filter(event_type=eventType)
        
        events = queryset.select_related('user').order_by('-created_at')[:limit]
        
        return [SecurityEventTypeType.from_model(event) for event in events]

    @strawberry.field
    def suspicious_activities(
        self,
        info: strawberry.types.Info,
        days: int = 7,
        limit: int = 100
    ) -> dict:
        """Get suspicious activities (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        # Get suspicious logins
        suspicious_logins = LoginHistory.get_suspicious_logins(days=days)
        
        # Get suspicious security events
        suspicious_events = SecurityEvent.get_suspicious_events(days=days)
        
        # Get high risk users
        from django.db.models import Avg
        high_risk_users = SecuritySettings.objects.filter(
            tenant=user.tenant,
            account_risk_score__gte=0.7
        ).select_related('user').order_by('-account_risk_score')[:10]
        
        return {
            'suspicious_logins': [LoginHistoryType.from_model(login) for login in suspicious_logins[:limit]],
            'suspicious_events': [SecurityEventTypeType.from_model(event) for event in suspicious_events[:limit]],
            'high_risk_users': [
                {
                    'userId': strawberry.ID(str(settings.user.id)),
                    'username': settings.user.username,
                    'riskScore': float(settings.account_risk_score)
                }
                for settings in high_risk_users
            ]
        }

    @strawberry.field
    def platform_security_stats(
        self,
        info: strawberry.types.Info,
        days: int = 30
    ) -> dict:
        """Get platform security statistics (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Login statistics
        login_stats = LoginHistory.objects.filter(
            tenant=user.tenant,
            logged_at__gte=cutoff_date
        ).values('result').annotate(count=Count('id'))
        
        # Security event statistics
        event_stats = SecurityEvent.objects.filter(
            tenant=user.tenant,
            created_at__gte=cutoff_date
        ).values('event_type').annotate(count=Count('id'))
        
        # 2FA usage statistics
        two_fa_enabled = SecuritySettings.objects.filter(
            tenant=user.tenant,
            two_fa_enabled=True
        ).count()
        
        total_users = SecuritySettings.objects.filter(tenant=user.tenant).count()
        
        # Device session statistics
        active_sessions = DeviceSession.objects.filter(
            tenant=user.tenant,
            status=SessionStatus.ACTIVE
        ).count()
        
        return {
            'period_days': days,
            'login_stats': {stat['result']: stat['count'] for stat in login_stats},
            'event_stats': {stat['event_type']: stat['count'] for stat in event_stats},
            'two_fa_usage': {
                'enabled': two_fa_enabled,
                'total_users': total_users,
                'adoption_rate': (two_fa_enabled / total_users * 100) if total_users > 0 else 0
            },
            'active_sessions': active_sessions
        }
