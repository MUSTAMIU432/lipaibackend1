import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import InetAddressField

from ..models import (
    SecuritySettings, TwoFAMethod,
    LoginHistory, LoginResult,
    DeviceSession, DeviceType, SessionStatus,
    SecurityEvent, SecurityEventType,
    TwoFAAttempt, TwoFAAttemptResult
)


# Security Settings Types
@strawberry.type
class SecuritySettingsType:
    id: strawberry.ID
    userId: strawberry.ID
    
    # Two Factor Auth
    twoFaEnabled: bool
    twoFaMethod: Optional[str]
    twoFaPhoneNumber: Optional[str]
    twoFaEmail: Optional[str]
    twoFaEnabledAt: Optional[datetime]
    twoFaLastUsedAt: Optional[datetime]
    
    # Backup Codes
    backupCodesRemaining: int
    backupCodesGeneratedAt: Optional[datetime]
    
    # Risk Scoring
    accountRiskScore: Decimal
    riskScoreUpdatedAt: Optional[datetime]
    riskFlags: List[str]
    
    # Login Preferences
    loginNotificationEmail: bool
    loginNotificationSms: bool
    trustedIps: List[str]
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: SecuritySettings):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            twoFaEnabled=instance.two_fa_enabled,
            twoFaMethod=instance.two_fa_method,
            twoFaPhoneNumber=instance.two_fa_phone_number,
            twoFaEmail=instance.two_fa_email,
            twoFaEnabledAt=instance.two_fa_enabled_at,
            twoFaLastUsedAt=instance.two_fa_last_used_at,
            backupCodesRemaining=instance.backup_codes_remaining,
            backupCodesGeneratedAt=instance.backup_codes_generated_at,
            accountRiskScore=instance.account_risk_score,
            riskScoreUpdatedAt=instance.risk_score_updated_at,
            riskFlags=instance.risk_flags,
            loginNotificationEmail=instance.login_notification_email,
            loginNotificationSms=instance.login_notification_sms,
            trustedIps=[str(ip) for ip in instance.trusted_ips],
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


# Login History Types
@strawberry.type
class LoginHistoryType:
    id: strawberry.ID
    userId: strawberry.ID
    result: str
    ipAddress: Optional[str]
    country: Optional[str]
    city: Optional[str]
    deviceType: str
    deviceName: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    userAgent: Optional[str]
    sessionId: Optional[strawberry.ID]
    twoFaUsed: bool
    twoFaMethod: Optional[str]
    failureReason: Optional[str]
    isSuspicious: bool
    suspiciousReason: Optional[str]
    loggedAt: datetime
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: LoginHistory):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            result=instance.result,
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            country=instance.country,
            city=instance.city,
            deviceType=instance.device_type,
            deviceName=instance.device_name,
            browser=instance.browser,
            os=instance.os,
            userAgent=instance.user_agent,
            sessionId=strawberry.ID(str(instance.session_id)) if instance.session_id else None,
            twoFaUsed=instance.two_fa_used,
            twoFaMethod=instance.two_fa_method,
            failureReason=instance.failure_reason,
            isSuspicious=instance.is_suspicious,
            suspiciousReason=instance.suspicious_reason,
            loggedAt=instance.logged_at,
            createdAt=instance.created_at,
        )


# Device Session Types
@strawberry.type
class DeviceSessionType:
    id: strawberry.ID
    userId: strawberry.ID
    refreshTokenId: Optional[strawberry.ID]
    
    # Device Detail
    deviceFingerprint: str
    deviceName: Optional[str]
    deviceType: str
    browser: Optional[str]
    os: Optional[str]
    userAgent: Optional[str]
    
    # Location
    ipAddress: Optional[str]
    country: Optional[str]
    city: Optional[str]
    
    # Trust
    isTrusted: bool
    trustedAt: Optional[datetime]
    
    # Status
    status: str
    lastActiveAt: datetime
    expiresAt: datetime
    revokedAt: Optional[datetime]
    revokedReason: Optional[str]
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: DeviceSession):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            refreshTokenId=strawberry.ID(str(instance.refresh_token_id)) if instance.refresh_token_id else None,
            deviceFingerprint=instance.device_fingerprint,
            deviceName=instance.device_name,
            deviceType=instance.device_type,
            browser=instance.browser,
            os=instance.os,
            userAgent=instance.user_agent,
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            country=instance.country,
            city=instance.city,
            isTrusted=instance.is_trusted,
            trustedAt=instance.trusted_at,
            status=instance.status,
            lastActiveAt=instance.last_active_at,
            expiresAt=instance.expires_at,
            revokedAt=instance.revoked_at,
            revokedReason=instance.revoked_reason,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


# Security Event Types
@strawberry.type
class SecurityEventType:
    id: strawberry.ID
    userId: strawberry.ID
    eventType: str
    description: Optional[str]
    ipAddress: Optional[str]
    deviceFingerprint: Optional[str]
    userAgent: Optional[str]
    metadata: dict
    riskScoreBefore: Optional[Decimal]
    riskScoreAfter: Optional[Decimal]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: SecurityEvent):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            eventType=instance.event_type,
            description=instance.description,
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            deviceFingerprint=instance.device_fingerprint,
            userAgent=instance.user_agent,
            metadata=instance.metadata,
            riskScoreBefore=instance.risk_score_before,
            riskScoreAfter=instance.risk_score_after,
            createdAt=instance.created_at,
        )


# Two FA Attempt Types
@strawberry.type
class TwoFAAttemptType:
    id: strawberry.ID
    userId: strawberry.ID
    method: str
    result: str
    ipAddress: Optional[str]
    expiresAt: datetime
    usedAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: TwoFAAttempt):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            method=instance.method,
            result=instance.result,
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            expiresAt=instance.expires_at,
            usedAt=instance.used_at,
            createdAt=instance.created_at,
        )


# Input Types
@strawberry.input
class TwoFASetupInput:
    method: str
    phoneNumber: Optional[str]
    email: Optional[str]


@strawberry.input
class TwoFAVerifyInput:
    code: str
    method: Optional[str]


@strawberry.input
class SecuritySettingsUpdateInput:
    loginNotificationEmail: Optional[bool]
    loginNotificationSms: Optional[bool]
    trustedIps: Optional[List[str]]


@strawberry.input
class DeviceSessionFilterInput:
    status: Optional[str] = None
    isTrusted: Optional[bool] = None
    deviceType: Optional[str] = None


@strawberry.input
class SecurityEventFilterInput:
    eventType: Optional[str] = None
    days: Optional[int] = 30


@strawberry.input
class LoginHistoryFilterInput:
    result: Optional[str] = None
    isSuspicious: Optional[bool] = None
    days: Optional[int] = 30
