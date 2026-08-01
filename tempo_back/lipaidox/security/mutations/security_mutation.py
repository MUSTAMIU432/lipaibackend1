import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import pyotp
import hashlib
import secrets

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
    TwoFASetupInput, TwoFAVerifyInput, SecuritySettingsUpdateInput
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
class SecurityMutation:
    # Two Factor Authentication Mutations
    @strawberry.mutation
    def setup_two_fa(self, info: strawberry.types.Info, input: TwoFASetupInput) -> dict:
        """Setup two-factor authentication"""
        user = require_auth(info)
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        if settings.two_fa_enabled:
            raise Exception("2FA is already enabled")
        
        # Generate secret for authenticator app
        if input.method == TwoFAMethod.AUTHENTICATOR_APP:
            secret = pyotp.random_base32()
            # Generate QR code data (in real implementation, you'd generate actual QR code)
            provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name="Lipaidox"
            )
            
            # Store secret temporarily (not enabled yet)
            settings.two_fa_secret = secret
            settings.save()
            
            return {
                "secret": secret,
                "provisioningUri": provisioning_uri,
                "backupCodes": self._generate_backup_codes(user)
            }
        
        # For SMS/Email, send verification code
        code = self._generate_2fa_code()
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Create 2FA attempt
        TwoFAAttempt.create_attempt(
            user=user,
            method=input.method,
            code_hash=code_hash,
            expires_minutes=10
        )
        
        # Send code (in real implementation, integrate with SMS/email service)
        if input.method == TwoFAMethod.SMS and input.phoneNumber:
            # Send SMS
            settings.two_fa_phone_number = input.phoneNumber
            settings.save()
            # TODO: Integrate with SMS service
        elif input.method == TwoFAMethod.EMAIL and input.email:
            # Send Email
            settings.two_fa_email = input.email
            settings.save()
            # TODO: Integrate with email service
        
        return {"message": f"Verification code sent via {input.method}"}

    @strawberry.mutation
    def verify_two_fa_setup(self, info: strawberry.types.Info, input: TwoFAVerifyInput) -> SecuritySettingsType:
        """Verify and enable two-factor authentication"""
        user = require_auth(info)
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        if settings.two_fa_enabled:
            raise Exception("2FA is already enabled")
        
        # For authenticator app verification
        if input.method == TwoFAMethod.AUTHENTICATOR_APP:
            if not settings.two_fa_secret:
                raise Exception("2FA setup not initiated")
            
            # Verify TOTP code
            totp = pyotp.TOTP(settings.two_fa_secret)
            if not totp.verify(input.code):
                # Log failed attempt
                SecurityEvent.create_event(
                    user=user,
                    event_type=SecurityEventType.TWO_FA_FAILED,
                    description="Failed 2FA setup verification",
                    metadata={'method': input.method}
                )
                raise Exception("Invalid verification code")
            
            # Enable 2FA
            settings.enable_2fa(input.method, settings.two_fa_secret)
            
            # Generate backup codes
            backup_codes = self._generate_backup_codes(user)
            settings.backup_codes_hash = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]
            settings.backup_codes_remaining = len(backup_codes)
            settings.backup_codes_generated_at = timezone.now()
            settings.save()
            
            # Log success
            SecurityEvent.create_event(
                user=user,
                event_type=SecurityEventType.TWO_FA_ENABLED,
                description="2FA enabled successfully",
                metadata={'method': input.method}
            )
            
            return SecuritySettingsType.from_model(settings)
        
        # For SMS/Email verification
        else:
            # Find the most recent attempt for this method
            attempt = TwoFAAttempt.objects.filter(
                user=user,
                method=input.method,
                result=TwoFAAttemptResult.FAILED
            ).order_by('-created_at').first()
            
            if not attempt or attempt.is_expired():
                raise Exception("Verification code expired or not found")
            
            # Verify code
            code_hash = hashlib.sha256(input.code.encode()).hexdigest()
            if code_hash != attempt.code_hash:
                attempt.result = TwoFAAttemptResult.FAILED
                attempt.save()
                
                SecurityEvent.create_event(
                    user=user,
                    event_type=SecurityEventType.TWO_FA_FAILED,
                    description="Failed 2FA setup verification",
                    metadata={'method': input.method}
                )
                raise Exception("Invalid verification code")
            
            # Mark attempt as used
            attempt.mark_success()
            
            # Enable 2FA
            settings.enable_2fa(input.method)
            
            # Log success
            SecurityEvent.create_event(
                user=user,
                event_type=SecurityEventType.TWO_FA_ENABLED,
                description="2FA enabled successfully",
                metadata={'method': input.method}
            )
            
            return SecuritySettingsType.from_model(settings)

    @strawberry.mutation
    def disable_two_fa(self, info: strawberry.types.Info, password: str) -> dict:
        """Disable two-factor authentication"""
        user = require_auth(info)
        
        # Verify password (in real implementation, check against user's password)
        if not user.check_password(password):
            raise Exception("Invalid password")
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        if not settings.two_fa_enabled:
            raise Exception("2FA is not enabled")
        
        old_method = settings.two_fa_method
        
        # Disable 2FA
        settings.disable_2fa()
        
        # Log event
        SecurityEvent.create_event(
            user=user,
            event_type=SecurityEventType.TWO_FA_DISABLED,
            description="2FA disabled by user",
            metadata={'previous_method': old_method}
        )
        
        return {"message": "2FA disabled successfully"}

    @strawberry.mutation
    def generate_backup_codes(self, info: strawberry.types.Info) -> List[str]:
        """Generate new backup codes"""
        user = require_auth(info)
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        if not settings.two_fa_enabled:
            raise Exception("2FA must be enabled to generate backup codes")
        
        # Generate new backup codes
        backup_codes = self._generate_backup_codes(user)
        settings.backup_codes_hash = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes]
        settings.backup_codes_remaining = len(backup_codes)
        settings.backup_codes_generated_at = timezone.now()
        settings.save()
        
        return backup_codes

    # Security Settings Mutations
    @strawberry.mutation
    def update_security_settings(self, info: strawberry.types.Info, input: SecuritySettingsUpdateInput) -> SecuritySettingsType:
        """Update security settings"""
        user = require_auth(info)
        
        settings = SecuritySettings.get_or_create_for_user(user)
        
        if input.loginNotificationEmail is not None:
            settings.login_notification_email = input.loginNotificationEmail
        
        if input.loginNotificationSms is not None:
            settings.login_notification_sms = input.loginNotificationSms
        
        if input.trustedIps is not None:
            settings.trusted_ips = input.trustedIps
        
        settings.save()
        
        return SecuritySettingsType.from_model(settings)

    # Device Session Mutations
    @strawberry.mutation
    def trust_device(self, info: strawberry.types.Info, sessionId: strawberry.ID) -> DeviceSessionType:
        """Trust a device"""
        user = require_auth(info)
        
        try:
            session = DeviceSession.objects.get(
                id=sessionId,
                user=user,
                status=SessionStatus.ACTIVE
            )
        except DeviceSession.DoesNotExist:
            raise Exception("Session not found or not active")
        
        session.trust_device()
        
        # Log event
        SecurityEvent.create_event(
            user=user,
            event_type=SecurityEventType.DEVICE_TRUSTED,
            description="Device marked as trusted",
            device_fingerprint=session.device_fingerprint,
            ip_address=session.ip_address
        )
        
        return DeviceSessionType.from_model(session)

    @strawberry.mutation
    def revoke_session(self, info: strawberry.types.Info, sessionId: strawberry.ID, reason: Optional[str] = None) -> dict:
        """Revoke a device session"""
        user = require_auth(info)
        
        try:
            session = DeviceSession.objects.get(
                id=sessionId,
                user=user
            )
        except DeviceSession.DoesNotExist:
            raise Exception("Session not found")
        
        session.revoke_session(reason or "User requested")
        
        # Log event
        SecurityEvent.create_event(
            user=user,
            event_type=SecurityEventType.SESSION_REVOKED,
            description=f"Session revoked: {reason or 'User requested'}",
            device_fingerprint=session.device_fingerprint
        )
        
        return {"message": "Session revoked successfully"}

    @strawberry.mutation
    def revoke_all_sessions(self, info: strawberry.types.Info, exceptCurrent: bool = False) -> dict:
        """Revoke all device sessions"""
        user = require_auth(info)
        
        current_session_id = None
        if exceptCurrent:
            # Get current session from request (implementation depends on your auth system)
            current_session_id = getattr(info.context.request, 'session_id', None)
        
        # Find current session
        current_session = None
        if current_session_id:
            try:
                current_session = DeviceSession.objects.get(id=current_session_id, user=user)
            except DeviceSession.DoesNotExist:
                current_session = None
        
        revoked_count = DeviceSession.revoke_all_user_sessions(user, current_session)
        
        # Log event
        SecurityEvent.create_event(
            user=user,
            event_type=SecurityEventType.SESSION_REVOKED,
            description=f"All sessions revoked ({revoked_count} sessions)"
        )
        
        return {"message": f"Revoked {revoked_count} sessions"}

    # Admin Mutations
    @strawberry.mutation
    def lock_user_account(self, info: strawberry.types.Info, userId: strawberry.ID, reason: Optional[str] = None) -> dict:
        """Lock user account (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        try:
            target_user = user.__class__.objects.get(id=userId)
        except user.__class__.DoesNotExist:
            raise Exception("User not found")
        
        # Lock account
        from datetime import timedelta
        target_user.locked_until = timezone.now() + timedelta(days=7)
        target_user.save()
        
        # Log event
        SecurityEvent.create_event(
            user=target_user,
            event_type=SecurityEventType.ACCOUNT_LOCKED,
            description=f"Account locked by admin: {reason or 'Security violation'}",
            metadata={'admin_id': user.id}
        )
        
        return {"message": f"User {target_user.username} locked successfully"}

    @strawberry.mutation
    def unlock_user_account(self, info: strawberry.types.Info, userId: strawberry.ID) -> dict:
        """Unlock user account (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        try:
            target_user = user.__class__.objects.get(id=userId)
        except user.__class__.DoesNotExist:
            raise Exception("User not found")
        
        # Unlock account
        target_user.locked_until = None
        target_user.save()
        
        # Log event
        SecurityEvent.create_event(
            user=target_user,
            event_type=SecurityEventType.ACCOUNT_UNLOCKED,
            description="Account unlocked by admin",
            metadata={'admin_id': user.id}
        )
        
        return {"message": f"User {target_user.username} unlocked successfully"}

    @strawberry.mutation
    def update_risk_score(self, info: strawberry.types.Info, userId: strawberry.ID, score: float, flags: Optional[List[str]] = None) -> SecuritySettingsType:
        """Update user risk score (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        try:
            target_user = user.__class__.objects.get(id=userId)
        except user.__class__.DoesNotExist:
            raise Exception("User not found")
        
        settings = SecuritySettings.get_or_create_for_user(target_user)
        
        old_score = settings.account_risk_score
        settings.update_risk_score(score, flags or [])
        
        # Log event
        SecurityEvent.create_event(
            user=target_user,
            event_type=SecurityEventType.SUSPICIOUS_LOGIN if score > 0.5 else SecurityEventType.LOGIN_SUCCESS,
            description=f"Risk score updated from {old_score} to {score}",
            risk_score_before=old_score,
            risk_score_after=score,
            metadata={'admin_id': user.id, 'flags': flags or []}
        )
        
        return SecuritySettingsType.from_model(settings)

    # Helper methods
    def _generate_2fa_code(self, length=6):
        """Generate 2FA verification code"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])

    def _generate_backup_codes(self, user, count=10):
        """Generate backup codes"""
        codes = []
        for _ in range(count):
            code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
            codes.append(code)
        return codes
