import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from ..models import (
    Notification, NotificationType, NotificationPriority,
    NotificationQueue, DeliveryChannel, NotificationStatus,
    NotificationPreference,
    NotificationTemplate, NotificationDeliveryLog
)


# Notification Types
@strawberry.type
class NotificationType:
    id: strawberry.ID
    recipientId: strawberry.ID
    senderId: Optional[strawberry.ID]
    
    # Content
    title: str
    message: str
    notificationType: str
    priority: str
    
    # Metadata
    entityType: Optional[str]
    entityId: Optional[strawberry.ID]
    actionUrl: Optional[str]
    actionText: Optional[str]
    metadata: dict
    
    # Status
    isRead: bool
    readAt: Optional[datetime]
    expiresAt: Optional[datetime]
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: Notification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            recipientId=strawberry.ID(str(instance.recipient_id)),
            senderId=strawberry.ID(str(instance.sender_id)) if instance.sender_id else None,
            title=instance.title,
            message=instance.message,
            notificationType=instance.notification_type,
            priority=instance.priority,
            entityType=instance.entity_type,
            entityId=strawberry.ID(str(instance.entity_id)) if instance.entity_id else None,
            actionUrl=instance.action_url,
            actionText=instance.action_text,
            metadata=instance.metadata,
            isRead=instance.is_read,
            readAt=instance.read_at,
            expiresAt=instance.expires_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class NotificationQueueType:
    id: strawberry.ID
    notificationId: strawberry.ID
    channel: str
    recipientAddress: str
    subject: Optional[str]
    content: str
    templateName: Optional[str]
    templateData: dict
    
    # Status
    status: str
    attempts: int
    maxAttempts: int
    lastAttemptAt: Optional[datetime]
    sentAt: Optional[datetime]
    deliveredAt: Optional[datetime]
    errorMessage: Optional[str]
    
    # Scheduling
    scheduledAt: Optional[datetime]
    priority: int
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: NotificationQueue):
        return cls(
            id=strawberry.ID(str(instance.id)),
            notificationId=strawberry.ID(str(instance.notification_id)),
            channel=instance.channel,
            recipientAddress=instance.recipient_address,
            subject=instance.subject,
            content=instance.content,
            templateName=instance.template_name,
            templateData=instance.template_data,
            status=instance.status,
            attempts=instance.attempts,
            maxAttempts=instance.max_attempts,
            lastAttemptAt=instance.last_attempt_at,
            sentAt=instance.sent_at,
            deliveredAt=instance.delivered_at,
            errorMessage=instance.error_message,
            scheduledAt=instance.scheduled_at,
            priority=instance.priority,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class NotificationPreferenceType:
    id: strawberry.ID
    userId: strawberry.ID
    
    # Email preferences
    emailNewSubscriber: bool
    emailNewTip: bool
    emailPpvPurchase: bool
    emailKycApproved: bool
    emailKycRejected: bool
    emailPayoutCompleted: bool
    emailNewContent: bool
    emailCreatorLive: bool
    emailAnnouncement: bool
    emailSystemUpdate: bool
    emailSecurityAlert: bool
    
    # Push preferences
    pushNewSubscriber: bool
    pushNewTip: bool
    pushPpvPurchase: bool
    pushKycApproved: bool
    pushKycRejected: bool
    pushPayoutCompleted: bool
    pushNewContent: bool
    pushCreatorLive: bool
    pushAnnouncement: bool
    pushSystemUpdate: bool
    pushSecurityAlert: bool
    
    # SMS preferences
    smsSecurityAlert: bool
    smsKycApproved: bool
    smsKycRejected: bool
    smsPayoutCompleted: bool
    
    # Global preferences
    doNotDisturb: bool
    doNotDisturbStart: Optional[str]
    doNotDisturbEnd: Optional[str]
    timezone: str
    maxDailyEmails: int
    maxDailyPush: int
    maxDailySms: int
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: NotificationPreference):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            emailNewSubscriber=instance.email_new_subscriber,
            emailNewTip=instance.email_new_tip,
            emailPpvPurchase=instance.email_ppv_purchase,
            emailKycApproved=instance.email_kyc_approved,
            emailKycRejected=instance.email_kyc_rejected,
            emailPayoutCompleted=instance.email_payout_completed,
            emailNewContent=instance.email_new_content,
            emailCreatorLive=instance.email_creator_live,
            emailAnnouncement=instance.email_announcement,
            emailSystemUpdate=instance.email_system_update,
            emailSecurityAlert=instance.email_security_alert,
            pushNewSubscriber=instance.push_new_subscriber,
            pushNewTip=instance.push_new_tip,
            pushPpvPurchase=instance.push_ppv_purchase,
            pushKycApproved=instance.push_kyc_approved,
            pushKycRejected=instance.push_kyc_rejected,
            pushPayoutCompleted=instance.push_payout_completed,
            pushNewContent=instance.push_new_content,
            pushCreatorLive=instance.push_creator_live,
            pushAnnouncement=instance.push_announcement,
            pushSystemUpdate=instance.push_system_update,
            pushSecurityAlert=instance.push_security_alert,
            smsSecurityAlert=instance.sms_security_alert,
            smsKycApproved=instance.sms_kyc_approved,
            smsKycRejected=instance.sms_kyc_rejected,
            smsPayoutCompleted=instance.sms_payout_completed,
            doNotDisturb=instance.do_not_disturb,
            doNotDisturbStart=instance.do_not_disturb_start.strftime('%H:%M') if instance.do_not_disturb_start else None,
            doNotDisturbEnd=instance.do_not_disturb_end.strftime('%H:%M') if instance.do_not_disturb_end else None,
            timezone=instance.timezone,
            maxDailyEmails=instance.max_daily_emails,
            maxDailyPush=instance.max_daily_push,
            maxDailySms=instance.max_daily_sms,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class NotificationTemplateType:
    id: strawberry.ID
    name: str
    notificationType: str
    channel: str
    subjectTemplate: Optional[str]
    bodyTemplate: str
    variablesSchema: dict
    isActive: bool
    priority: int
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: NotificationTemplate):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            notificationType=instance.notification_type,
            channel=instance.channel,
            subjectTemplate=instance.subject_template,
            bodyTemplate=instance.body_template,
            variablesSchema=instance.variables_schema,
            isActive=instance.is_active,
            priority=instance.priority,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class NotificationDeliveryLogType:
    id: strawberry.ID
    notificationId: strawberry.ID
    queueEntryId: Optional[strawberry.ID]
    channel: str
    recipientAddress: str
    status: str
    sentAt: Optional[datetime]
    deliveredAt: Optional[datetime]
    errorMessage: Optional[str]
    response_data: dict
    provider: Optional[str]
    externalId: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: NotificationDeliveryLog):
        return cls(
            id=strawberry.ID(str(instance.id)),
            notificationId=strawberry.ID(str(instance.notification_id)),
            queueEntryId=strawberry.ID(str(instance.queue_entry_id)) if instance.queue_entry_id else None,
            channel=instance.channel,
            recipientAddress=instance.recipient_address,
            status=instance.status,
            sentAt=instance.sent_at,
            deliveredAt=instance.delivered_at,
            errorMessage=instance.error_message,
            response_data=instance.response_data,
            provider=instance.provider,
            externalId=instance.external_id,
            createdAt=instance.created_at,
        )


# Input Types
@strawberry.input
class NotificationCreateInput:
    recipientId: strawberry.ID
    title: str
    message: str
    notificationType: str
    priority: Optional[str]
    entityType: Optional[str]
    entityId: Optional[strawberry.ID]
    actionUrl: Optional[str]
    actionText: Optional[str]
    metadata: Optional[dict]
    expiresAt: Optional[datetime]


@strawberry.input
class BulkNotificationInput:
    recipientIds: List[strawberry.ID]
    title: str
    message: str
    notificationType: str
    priority: Optional[str]
    entityType: Optional[str]
    entityId: Optional[strawberry.ID]
    actionUrl: Optional[str]
    actionText: Optional[str]
    metadata: Optional[dict]


@strawberry.input
class NotificationPreferencesUpdateInput:
    # Email preferences
    emailNewSubscriber: Optional[bool]
    emailNewTip: Optional[bool]
    emailPpvPurchase: Optional[bool]
    emailKycApproved: Optional[bool]
    emailKycRejected: Optional[bool]
    emailPayoutCompleted: Optional[bool]
    emailNewContent: Optional[bool]
    emailCreatorLive: Optional[bool]
    emailAnnouncement: Optional[bool]
    emailSystemUpdate: Optional[bool]
    emailSecurityAlert: Optional[bool]
    
    # Push preferences
    pushNewSubscriber: Optional[bool]
    pushNewTip: Optional[bool]
    pushPpvPurchase: Optional[bool]
    pushKycApproved: Optional[bool]
    pushKycRejected: Optional[bool]
    pushPayoutCompleted: Optional[bool]
    pushNewContent: Optional[bool]
    pushCreatorLive: Optional[bool]
    pushAnnouncement: Optional[bool]
    pushSystemUpdate: Optional[bool]
    pushSecurityAlert: Optional[bool]
    
    # SMS preferences
    smsSecurityAlert: Optional[bool]
    smsKycApproved: Optional[bool]
    smsKycRejected: Optional[bool]
    smsPayoutCompleted: Optional[bool]
    
    # Global preferences
    doNotDisturb: Optional[bool]
    doNotDisturbStart: Optional[str]
    doNotDisturbEnd: Optional[str]
    timezone: Optional[str]
    maxDailyEmails: Optional[int]
    maxDailyPush: Optional[int]
    maxDailySms: Optional[int]


@strawberry.input
class NotificationFilterInput:
    unreadOnly: Optional[bool]
    notificationType: Optional[str]
    priority: Optional[str]
    limit: Optional[int]


# Analytics Types
@strawberry.type
class NotificationStats:
    totalNotifications: int
    unreadCount: int
    byType: dict
    byPriority: dict
    deliveryStats: dict
