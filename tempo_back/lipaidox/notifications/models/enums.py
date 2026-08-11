import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class NotificationType(models.TextChoices):
    """Types of notifications"""
    # Creator notifications
    NEW_SUBSCRIBER = 'new_subscriber', 'New Subscriber'
    SUBSCRIBER_CANCELLED = 'subscriber_cancelled', 'Subscriber Cancelled'
    NEW_TIP_RECEIVED = 'new_tip_received', 'New Tip Received'
    NEW_PPV_PURCHASE = 'new_ppv_purchase', 'New PPV Purchase'
    NEW_FOLLOWER = 'new_follower', 'New Follower'
    NEW_COMMENT = 'new_comment', 'New Comment'
    NEW_LIKE = 'new_like', 'New Like'
    PAYOUT_COMPLETED = 'payout_completed', 'Payout Completed'
    PAYOUT_FAILED = 'payout_failed', 'Payout Failed'
    KYC_APPROVED = 'kyc_approved', 'KYC Approved'
    KYC_REJECTED = 'kyc_rejected', 'KYC Rejected'
    KYC_RESUBMISSION_REQUESTED = 'kyc_resubmission_requested', 'KYC Resubmission Requested'
    CREDIT_GIFTED = 'credit_gifted', 'Credit Gifted'
    PLAN_RENEWED = 'plan_renewed', 'Plan Renewed'
    PLAN_CANCELLED = 'plan_cancelled', 'Plan Cancelled'
    PLAN_EXPIRED = 'plan_expired', 'Plan Expired'
    
    # Fan notifications
    CREATOR_WENT_LIVE = 'creator_went_live', 'Creator Went Live'
    NEW_CONTENT_POSTED = 'new_content_posted', 'New Content Posted'
    CONTENT_UNLOCKED = 'content_unlocked', 'Content Unlocked'
    SUBSCRIPTION_RENEWED = 'subscription_renewed', 'Subscription Renewed'
    SUBSCRIPTION_EXPIRING = 'subscription_expiring', 'Subscription Expiring'
    TIP_SENT_CONFIRMED = 'tip_sent_confirmed', 'Tip Sent Confirmed'
    CREDITS_PURCHASED = 'credits_purchased', 'Credits Purchased'
    
    # Platform notifications
    ANNOUNCEMENT = 'announcement', 'Announcement'
    SECURITY_ALERT = 'security_alert', 'Security Alert'
    ACCOUNT_SUSPENDED = 'account_suspended', 'Account Suspended'
    ACCOUNT_REACTIVATED = 'account_reactivated', 'Account Reactivated'
    PASSWORD_CHANGED = 'password_changed', 'Password Changed'
    NEW_LOGIN_DETECTED = 'new_login_detected', 'New Login Detected'


class NotificationChannel(models.TextChoices):
    """Notification delivery channels"""
    IN_APP = 'in_app', 'In-App'
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'
    PUSH = 'push', 'Push'


# The queue/template models and the GraphQL schema import this name for the same
# set of channels. Kept as an alias rather than a second enum so the two can
# never drift apart.
DeliveryChannel = NotificationChannel


class NotificationStatus(models.TextChoices):
    """Notification status"""
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    DELIVERED = 'delivered', 'Delivered'
    READ = 'read', 'Read'
    FAILED = 'failed', 'Failed'
    DISMISSED = 'dismissed', 'Dismissed'


class NotificationPriority(models.TextChoices):
    """Notification priority levels"""
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'
