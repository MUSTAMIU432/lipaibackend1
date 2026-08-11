import strawberry
from strawberry.scalars import JSON
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, datetime
import json

from ..models import (
    Notification, NotificationType, NotificationPriority,
    NotificationQueue, DeliveryChannel, NotificationStatus,
    NotificationPreference,
    NotificationTemplate, NotificationDeliveryLog
)

from ..schema.notification_schema import (
    # Types
    NotificationType as NotificationGraphQLType, NotificationQueueType,
    NotificationPreferenceType, NotificationTemplateType,
    NotificationDeliveryLogType,
    
    # Input Types
    NotificationCreateInput, BulkNotificationInput,
    NotificationPreferencesUpdateInput
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
class NotificationMutation:
    # Notification Mutations
    @strawberry.mutation
    def create_notification(self, info: strawberry.types.Info, input: NotificationCreateInput) -> NotificationGraphQLType:
        """Create a single notification"""
        user = require_auth(info)
        
        # Get recipient
        try:
            recipient = user.__class__.objects.get(id=input.recipientId)
        except user.__class__.DoesNotExist:
            raise Exception("Recipient not found")
        
        # Check permissions (admin can create for anyone, users can only create for themselves)
        if user.id != recipient.id and user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Cannot create notifications for other users")
        
        # Create notification
        notification = Notification.create_notification(
            recipient=recipient,
            title=input.title,
            message=input.message,
            notification_type=input.notificationType,
            priority=input.priority or NotificationPriority.NORMAL,
            entity_type=input.entityType,
            entity_id=input.entityId,
            action_url=input.actionUrl,
            action_text=input.actionText,
            metadata=input.metadata or {},
            expires_at=input.expiresAt
        )
        
        # Queue for delivery based on user preferences
        self._queue_notification_delivery(notification)
        
        return NotificationGraphQLType.from_model(notification)

    @strawberry.mutation
    def create_bulk_notifications(self, info: strawberry.types.Info, input: BulkNotificationInput) -> List[NotificationGraphQLType]:
        """Create notifications for multiple recipients"""
        user = require_auth(info)
        
        # Check permissions (admin only)
        require_admin(user)
        
        # Get recipients
        recipients = user.__class__.objects.filter(id__in=input.recipientIds)
        
        if recipients.count() != len(input.recipientIds):
            raise Exception("Some recipients not found")
        
        # Create notifications
        notifications = Notification.bulk_create_notifications(
            recipients=recipients,
            title=input.title,
            message=input.message,
            notification_type=input.notificationType,
            priority=input.priority or NotificationPriority.NORMAL,
            entity_type=input.entityType,
            entity_id=input.entityId,
            action_url=input.actionUrl,
            action_text=input.actionText,
            metadata=input.metadata or {}
        )
        
        # Queue for delivery
        for notification in notifications:
            self._queue_notification_delivery(notification)
        
        return [NotificationGraphQLType.from_model(notification) for notification in notifications]

    @strawberry.mutation
    def mark_notification_read(self, info: strawberry.types.Info, notificationId: strawberry.ID) -> NotificationGraphQLType:
        """Mark notification as read"""
        user = require_auth(info)
        
        try:
            notification = Notification.objects.get(
                id=notificationId,
                recipient=user
            )
        except Notification.DoesNotExist:
            raise Exception("Notification not found")
        
        notification.mark_read()
        
        return NotificationGraphQLType.from_model(notification)

    @strawberry.mutation
    def mark_all_notifications_read(self, info: strawberry.types.Info) -> JSON:
        """Mark all notifications as read"""
        user = require_auth(info)
        
        count = Notification.mark_all_read(user)
        
        return {"message": f"Marked {count} notifications as read"}

    @strawberry.mutation
    def delete_notification(self, info: strawberry.types.Info, notificationId: strawberry.ID) -> JSON:
        """Delete a notification"""
        user = require_auth(info)
        
        try:
            notification = Notification.objects.get(
                id=notificationId,
                recipient=user
            )
        except Notification.DoesNotExist:
            raise Exception("Notification not found")
        
        notification.delete()
        
        return {"message": "Notification deleted successfully"}

    # Notification Preferences Mutations
    @strawberry.mutation
    def update_notification_preferences(self, info: strawberry.types.Info, input: NotificationPreferencesUpdateInput) -> NotificationPreferenceType:
        """Update notification preferences"""
        user = require_auth(info)
        
        preferences = NotificationPreference.get_or_create_for_user(user)
        
        # Update preferences based on input
        preferences_dict = {}
        
        # Email preferences
        if input.emailNewSubscriber is not None:
            preferences_dict['email_new_subscriber'] = input.emailNewSubscriber
        if input.emailNewTip is not None:
            preferences_dict['email_new_tip'] = input.emailNewTip
        if input.emailPpvPurchase is not None:
            preferences_dict['email_ppv_purchase'] = input.emailPpvPurchase
        if input.emailKycApproved is not None:
            preferences_dict['email_kyc_approved'] = input.emailKycApproved
        if input.emailKycRejected is not None:
            preferences_dict['email_kyc_rejected'] = input.emailKycRejected
        if input.emailPayoutCompleted is not None:
            preferences_dict['email_payout_completed'] = input.emailPayoutCompleted
        if input.emailNewContent is not None:
            preferences_dict['email_new_content'] = input.emailNewContent
        if input.emailCreatorLive is not None:
            preferences_dict['email_creator_live'] = input.emailCreatorLive
        if input.emailAnnouncement is not None:
            preferences_dict['email_announcement'] = input.emailAnnouncement
        if input.emailSystemUpdate is not None:
            preferences_dict['email_system_update'] = input.emailSystemUpdate
        if input.emailSecurityAlert is not None:
            preferences_dict['email_security_alert'] = input.emailSecurityAlert
        
        # Push preferences
        if input.pushNewSubscriber is not None:
            preferences_dict['push_new_subscriber'] = input.pushNewSubscriber
        if input.pushNewTip is not None:
            preferences_dict['push_new_tip'] = input.pushNewTip
        if input.pushPpvPurchase is not None:
            preferences_dict['push_ppv_purchase'] = input.pushPpvPurchase
        if input.pushKycApproved is not None:
            preferences_dict['push_kyc_approved'] = input.pushKycApproved
        if input.pushKycRejected is not None:
            preferences_dict['push_kyc_rejected'] = input.pushKycRejected
        if input.pushPayoutCompleted is not None:
            preferences_dict['push_payout_completed'] = input.pushPayoutCompleted
        if input.pushNewContent is not None:
            preferences_dict['push_new_content'] = input.pushNewContent
        if input.pushCreatorLive is not None:
            preferences_dict['push_creator_live'] = input.pushCreatorLive
        if input.pushAnnouncement is not None:
            preferences_dict['push_announcement'] = input.pushAnnouncement
        if input.pushSystemUpdate is not None:
            preferences_dict['push_system_update'] = input.pushSystemUpdate
        if input.pushSecurityAlert is not None:
            preferences_dict['push_security_alert'] = input.pushSecurityAlert
        
        # SMS preferences
        if input.smsSecurityAlert is not None:
            preferences_dict['sms_security_alert'] = input.smsSecurityAlert
        if input.smsKycApproved is not None:
            preferences_dict['sms_kyc_approved'] = input.smsKycApproved
        if input.smsKycRejected is not None:
            preferences_dict['sms_kyc_rejected'] = input.smsKycRejected
        if input.smsPayoutCompleted is not None:
            preferences_dict['sms_payout_completed'] = input.smsPayoutCompleted
        
        # Global preferences
        if input.doNotDisturb is not None:
            preferences_dict['do_not_disturb'] = input.doNotDisturb
        if input.doNotDisturbStart is not None:
            preferences_dict['do_not_disturb_start'] = datetime.strptime(input.doNotDisturbStart, '%H:%M').time()
        if input.doNotDisturbEnd is not None:
            preferences_dict['do_not_disturb_end'] = datetime.strptime(input.doNotDisturbEnd, '%H:%M').time()
        if input.timezone is not None:
            preferences_dict['timezone'] = input.timezone
        if input.maxDailyEmails is not None:
            preferences_dict['max_daily_emails'] = input.maxDailyEmails
        if input.maxDailyPush is not None:
            preferences_dict['max_daily_push'] = input.maxDailyPush
        if input.maxDailySms is not None:
            preferences_dict['max_daily_sms'] = input.maxDailySms
        
        # Update preferences
        NotificationPreference.bulk_update_preferences(user, preferences_dict)
        
        # Get updated preferences
        updated_preferences = NotificationPreference.get_or_create_for_user(user)
        
        return NotificationPreferenceType.from_model(updated_preferences)

    # Template Mutations
    @strawberry.mutation
    def create_notification_template(
        self,
        info: strawberry.types.Info,
        name: str,
        notificationType: str,
        channel: str,
        subjectTemplate: Optional[str],
        bodyTemplate: str,
        variablesSchema: Optional[JSON]
    ) -> NotificationTemplateType:
        """Create notification template (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        template = NotificationTemplate.objects.create(
            tenant=user.tenant,
            name=name,
            notification_type=notificationType,
            channel=channel,
            subject_template=subjectTemplate,
            body_template=bodyTemplate,
            variables_schema=variablesSchema or {}
        )
        
        return NotificationTemplateType.from_model(template)

    @strawberry.mutation
    def update_notification_template(
        self,
        info: strawberry.types.Info,
        templateId: strawberry.ID,
        name: Optional[str],
        subjectTemplate: Optional[str],
        bodyTemplate: Optional[str],
        variablesSchema: Optional[JSON],
        isActive: Optional[bool]
    ) -> NotificationTemplateType:
        """Update notification template (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        try:
            template = NotificationTemplate.objects.get(
                id=templateId,
                tenant=user.tenant
            )
        except NotificationTemplate.DoesNotExist:
            raise Exception("Template not found")
        
        if name is not None:
            template.name = name
        if subjectTemplate is not None:
            template.subject_template = subjectTemplate
        if bodyTemplate is not None:
            template.body_template = bodyTemplate
        if variablesSchema is not None:
            template.variables_schema = variablesSchema
        if isActive is not None:
            template.is_active = isActive
        
        template.save()
        
        return NotificationTemplateType.from_model(template)

    # Queue Management Mutations
    @strawberry.mutation
    def retry_failed_notifications(self, info: strawberry.types.Info, channel: Optional[str] = None) -> JSON:
        """Retry failed notifications (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        failed_notifications = NotificationQueue.get_failed_notifications(channel=channel)
        
        retried_count = 0
        for notification in failed_notifications:
            if notification.can_retry():
                notification.status = NotificationStatus.PENDING
                notification.attempts = 0
                notification.error_message = None
                notification.save()
                retried_count += 1
        
        return {"message": f"Retried {retried_count} failed notifications"}

    @strawberry.mutation
    def cleanup_old_notifications(self, info: strawberry.types.Info, days: int = 30) -> JSON:
        """Clean up old notifications (admin only)"""
        user = require_auth(info)
        require_admin(user)
        
        # Clean up expired notifications
        expired_count = Notification.cleanup_expired_notifications()
        
        # Clean up old queue entries
        queue_count = NotificationQueue.cleanup_old_notifications(days=days)
        
        return {
            "message": f"Cleaned up {expired_count} expired notifications and {queue_count} old queue entries"
        }

    # Helper methods
    def _queue_notification_delivery(self, notification):
        """Queue notification for delivery based on user preferences"""
        preferences = NotificationPreference.get_or_create_for_user(notification.recipient)
        
        # Get enabled channels for this notification type
        enabled_channels = preferences.get_enabled_channels(notification.notification_type)
        
        # Check do not disturb
        if preferences.is_do_not_disturb_active():
            # Only allow urgent notifications during DND
            if notification.priority != NotificationPriority.URGENT:
                return
        
        # Queue for each enabled channel
        for channel in enabled_channels:
            recipient_address = self._get_recipient_address(notification.recipient, channel)
            
            if recipient_address:
                # Get template
                template = NotificationTemplate.get_template(
                    notification.notification_type,
                    channel
                )
                
                if template:
                    # Render template
                    context = {
                        'recipient_name': notification.recipient.username,
                        'title': notification.title,
                        'message': notification.message,
                        'action_url': notification.action_url,
                        'action_text': notification.action_text,
                        **notification.metadata
                    }
                    
                    rendered = template.render(context)
                    subject = rendered.get('subject')
                    content = rendered.get('body')
                else:
                    # Use default content
                    subject = notification.title if channel == DeliveryChannel.EMAIL else None
                    content = notification.message
                
                # Create queue entry
                NotificationQueue.queue_notification(
                    notification=notification,
                    channel=channel,
                    recipient_address=recipient_address,
                    subject=subject,
                    content=content,
                    template_name=template.name if template else None,
                    template_data=context if template else {},
                    priority=5 if notification.priority == NotificationPriority.URGENT else 1
                )

    def _get_recipient_address(self, user, channel):
        """Get recipient address for channel"""
        if channel == DeliveryChannel.EMAIL:
            return user.email
        elif channel == DeliveryChannel.SMS:
            # Get phone number from user profile or security settings
            try:
                from lipaidox.security.models import SecuritySettings
                security_settings = SecuritySettings.objects.get(user=user)
                return security_settings.two_fa_phone_number
            except SecuritySettings.DoesNotExist:
                return None
        elif channel == DeliveryChannel.PUSH:
            # Return device token (implementation depends on push service)
            return user.email  # Placeholder
        
        return None
