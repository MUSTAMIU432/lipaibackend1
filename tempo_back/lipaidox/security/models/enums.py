import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class TwoFAMethod(models.TextChoices):
    """Two Factor Authentication methods"""
    SMS = 'sms', 'SMS'
    EMAIL = 'email', 'Email'
    AUTHENTICATOR_APP = 'authenticator_app', 'Authenticator App'
    BACKUP_CODE = 'backup_code', 'Backup Code'


class LoginResult(models.TextChoices):
    """Login attempt results"""
    SUCCESS = 'success', 'Success'
    FAILED_PASSWORD = 'failed_password', 'Failed Password'
    FAILED_2FA = 'failed_2fa', 'Failed 2FA'
    FAILED_LOCKED = 'failed_locked', 'Failed Locked'
    FAILED_SUSPENDED = 'failed_suspended', 'Failed Suspended'
    FAILED_UNVERIFIED = 'failed_unverified', 'Failed Unverified'


class DeviceType(models.TextChoices):
    """Device types"""
    MOBILE = 'mobile', 'Mobile'
    TABLET = 'tablet', 'Tablet'
    DESKTOP = 'desktop', 'Desktop'
    UNKNOWN = 'unknown', 'Unknown'


class SecurityEventType(models.TextChoices):
    """Security event types"""
    LOGIN_SUCCESS = 'login_success', 'Login Success'
    LOGIN_FAILED = 'login_failed', 'Login Failed'
    PASSWORD_CHANGED = 'password_changed', 'Password Changed'
    EMAIL_CHANGED = 'email_changed', 'Email Changed'
    PHONE_CHANGED = 'phone_changed', 'Phone Changed'
    TWO_FA_ENABLED = 'two_fa_enabled', '2FA Enabled'
    TWO_FA_DISABLED = 'two_fa_disabled', '2FA Disabled'
    TWO_FA_FAILED = 'two_fa_failed', '2FA Failed'
    DEVICE_ADDED = 'device_added', 'Device Added'
    DEVICE_REMOVED = 'device_removed', 'Device Removed'
    DEVICE_TRUSTED = 'device_trusted', 'Device Trusted'
    SUSPICIOUS_LOGIN = 'suspicious_login', 'Suspicious Login'
    ACCOUNT_LOCKED = 'account_locked', 'Account Locked'
    ACCOUNT_UNLOCKED = 'account_unlocked', 'Account Unlocked'
    SESSION_REVOKED = 'session_revoked', 'Session Revoked'
    PASSWORD_RESET_REQUESTED = 'password_reset_requested', 'Password Reset Requested'
    PASSWORD_RESET_COMPLETED = 'password_reset_completed', 'Password Reset Completed'


class SessionStatus(models.TextChoices):
    """Device session status"""
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    REVOKED = 'revoked', 'Revoked'
    LOGGED_OUT = 'logged_out', 'Logged Out'


class TwoFAAttemptResult(models.TextChoices):
    """2FA attempt results"""
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'
    ALREADY_USED = 'already_used', 'Already Used'
