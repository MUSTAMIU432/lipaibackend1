import uuid
from django.db import models
from multitenant.models import TenantAwareModel
from .enums import NotificationType


class NotificationPreference(TenantAwareModel):
    """
    Notification Preferences - Module 17
    User preferences for different notification types matching the provided schema
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )

    # Global Toggles
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)

    # Per Event Type Toggles
    notify_new_subscriber = models.BooleanField(default=True)
    notify_new_tip = models.BooleanField(default=True)
    notify_new_ppv_purchase = models.BooleanField(default=True)
    notify_new_follower = models.BooleanField(default=True)
    notify_new_comment = models.BooleanField(default=True)
    notify_new_like = models.BooleanField(default=False)
    notify_payout_completed = models.BooleanField(default=True)
    notify_payout_failed = models.BooleanField(default=True)
    notify_kyc_updates = models.BooleanField(default=True)
    notify_creator_went_live = models.BooleanField(default=True)
    notify_new_content_posted = models.BooleanField(default=True)
    notify_subscription_expiring = models.BooleanField(default=True)
    notify_security_alerts = models.BooleanField(default=True)
    notify_announcements = models.BooleanField(default=True)
    notify_plan_updates = models.BooleanField(default=True)

    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    quiet_hours_timezone = models.CharField(max_length=100, null=True, blank=True)

    # Email Digest
    email_digest_enabled = models.BooleanField(default=False)
    email_digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly')
        ],
        default='daily'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'
        app_label = 'lipaidox_notifications'
        indexes = [
            models.Index(fields=['user'], name='idx_notification_prefs_user_id'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['user'], name='notification_preferences_user_unique'),
        ]

    def __str__(self):
        return f"Notification Preferences: {self.user.username}"

    def is_enabled_for_type(self, notification_type):
        """Check if notification type is enabled"""
        field_map = {
            NotificationType.NEW_SUBSCRIBER: 'notify_new_subscriber',
            NotificationType.NEW_TIP_RECEIVED: 'notify_new_tip',
            NotificationType.NEW_PPV_PURCHASE: 'notify_new_ppv_purchase',
            NotificationType.NEW_FOLLOWER: 'notify_new_follower',
            NotificationType.NEW_COMMENT: 'notify_new_comment',
            NotificationType.NEW_LIKE: 'notify_new_like',
            NotificationType.PAYOUT_COMPLETED: 'notify_payout_completed',
            NotificationType.PAYOUT_FAILED: 'notify_payout_failed',
            NotificationType.KYC_APPROVED: 'notify_kyc_updates',
            NotificationType.KYC_REJECTED: 'notify_kyc_updates',
            NotificationType.KYC_RESUBMISSION_REQUESTED: 'notify_kyc_updates',
            NotificationType.CREATOR_WENT_LIVE: 'notify_creator_went_live',
            NotificationType.NEW_CONTENT_POSTED: 'notify_new_content_posted',
            NotificationType.SUBSCRIPTION_RENEWED: 'notify_plan_updates',
            NotificationType.SUBSCRIPTION_EXPIRING: 'notify_subscription_expiring',
            NotificationType.PLAN_RENEWED: 'notify_plan_updates',
            NotificationType.PLAN_CANCELLED: 'notify_plan_updates',
            NotificationType.PLAN_EXPIRED: 'notify_plan_updates',
            NotificationType.SECURITY_ALERT: 'notify_security_alerts',
            NotificationType.ANNOUNCEMENT: 'notify_announcements',
            NotificationType.ACCOUNT_SUSPENDED: 'notify_security_alerts',
            NotificationType.ACCOUNT_REACTIVATED: 'notify_security_alerts',
            NotificationType.PASSWORD_CHANGED: 'notify_security_alerts',
            NotificationType.NEW_LOGIN_DETECTED: 'notify_security_alerts',
        }
        
        field_name = field_map.get(notification_type)
        if field_name:
            return getattr(self, field_name, False)
        
        return True  # Default to enabled for unknown types

    def is_quiet_hours_active(self):
        """Check if quiet hours are currently active"""
        if not self.quiet_hours_enabled:
            return False
        
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        from django.utils import timezone
        import pytz
        
        # Get user's timezone or default to UTC
        tz_name = self.quiet_hours_timezone or 'UTC'
        try:
            tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.UTC
        
        current_time = timezone.now().astimezone(tz).time()
        start_time = self.quiet_hours_start
        end_time = self.quiet_hours_end
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:  # Overnight period
            return current_time >= start_time or current_time <= end_time

    def can_send_notification(self, notification_type, channel):
        """Check if notification can be sent"""
        # Check channel is enabled
        if channel == 'in_app' and not self.in_app_enabled:
            return False
        elif channel == 'email' and not self.email_enabled:
            return False
        elif channel == 'sms' and not self.sms_enabled:
            return False
        elif channel == 'push' and not self.push_enabled:
            return False
        
        # Check notification type is enabled
        if not self.is_enabled_for_type(notification_type):
            return False
        
        # Check quiet hours (except for urgent notifications)
        if self.is_quiet_hours_active():
            # Allow urgent notifications during quiet hours
            urgent_types = [
                NotificationType.SECURITY_ALERT,
                NotificationType.ACCOUNT_SUSPENDED,
                NotificationType.PASSWORD_CHANGED,
            ]
            if notification_type not in urgent_types:
                return False
        
        return True

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create notification preferences for user"""
        preferences, created = cls.objects.get_or_create(
            user=user,
            tenant=user.tenant
        )
        return preferences

    @classmethod
    def bulk_update_preferences(cls, user, preferences_dict):
        """Bulk update notification preferences"""
        preferences = cls.get_or_create_for_user(user)
        
        for field_name, value in preferences_dict.items():
            if hasattr(preferences, field_name):
                setattr(preferences, field_name, value)
        
        preferences.save()
        return preferences
