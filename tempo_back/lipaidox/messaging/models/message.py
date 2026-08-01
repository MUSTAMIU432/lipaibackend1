import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class MessageType(models.TextChoices):
    """Message types"""
    TEXT = 'text', 'Text'
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    AUDIO = 'audio', 'Audio'
    FILE = 'file', 'File'
    TIP = 'tip', 'Tip'
    AUTOMATED = 'automated', 'Automated'


class MessageStatus(models.TextChoices):
    """Message status"""
    SENT = 'sent', 'Sent'
    DELIVERED = 'delivered', 'Delivered'
    READ = 'read', 'Read'
    FAILED = 'failed', 'Failed'
    DELETED = 'deleted', 'Deleted'


class Message(TenantAwareModel):
    """
    Messages - Module 20
    Individual messages in conversations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )

    # Content
    body = models.TextField(null=True, blank=True)
    is_automated = models.BooleanField(default=False)
    auto_dm_rule = models.ForeignKey(
        'AutoDMRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_messages'
    )

    # Reply
    reply_to_message = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies'
    )

    # Rich content (mirrors frontend message shape)
    images = models.JSONField(default=list, blank=True)        # list[str] of image urls
    links = models.JSONField(default=list, blank=True)         # list[{url,title,description,image,domain}]
    voice_note = models.JSONField(null=True, blank=True)       # {url, duration, waveform}
    video_note = models.JSONField(null=True, blank=True)       # {url, duration, thumbnail}

    # Editing
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    # Disappearing messages
    disappear_after = models.CharField(max_length=10, default='off')  # off|1h|24h|7d|30d|custom
    expires_at = models.DateTimeField(null=True, blank=True)

    # Tip Message (commented out until tip model exists)
    # tip = models.ForeignKey(
    #     'lipaidox_monetization.Tip',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='tip_messages'
    # )
    tip_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Status
    status = models.CharField(
        max_length=15,
        choices=MessageStatus.choices,
        default=MessageStatus.SENT
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Deletion
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_receiver = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messages'
        app_label = 'lipaidox_messaging'
        indexes = [
            models.Index(fields=['conversation'], name='idx_messages_conversation_id'),
            models.Index(fields=['sender'], name='idx_messages_sender_id'),
            models.Index(fields=['status'], name='idx_messages_status'),
            models.Index(fields=['-sent_at'], name='idx_messages_sent_at'),
            models.Index(fields=['is_automated'], name='idx_messages_is_automated'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(body__isnull=False) | ~models.Q(message_type='text'),
                name='body_or_attachment'
            ),
        ]

    def __str__(self):
        return f"Message: {self.sender.username} in conversation {self.conversation.id}"

    def mark_delivered(self):
        """Mark message as delivered"""
        from django.utils import timezone
        
        self.status = MessageStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save()

    def mark_read(self):
        """Mark message as read"""
        from django.utils import timezone
        
        self.status = MessageStatus.READ
        self.read_at = timezone.now()
        self.save()

    def mark_failed(self):
        """Mark message as failed"""
        self.status = MessageStatus.FAILED
        self.save()

    def delete_for_user(self, user):
        """Delete message for specific user"""
        from django.utils import timezone
        
        if user == self.sender:
            self.is_deleted_by_sender = True
        else:
            # Check if user is the receiver (fan or creator in conversation)
            if (self.conversation.fan == user) or (self.conversation.creator == user):
                self.is_deleted_by_receiver = True
        
        # If deleted by both sides, mark as deleted
        if self.is_deleted_by_sender and self.is_deleted_by_receiver:
            self.status = MessageStatus.DELETED
            self.deleted_at = timezone.now()
        
        self.save()

    @classmethod
    def create_message(cls, conversation, sender, body=None, message_type=MessageType.TEXT, **kwargs):
        """Create a new message"""
        message = cls.objects.create(
            conversation=conversation,
            tenant=conversation.tenant,
            sender=sender,
            body=body,
            message_type=message_type,
            **kwargs
        )
        
        # Update conversation's last message
        conversation.update_last_message(message)
        
        # Update unread count
        if sender == conversation.fan:
            conversation.increment_unread_count('creator')
        else:
            conversation.increment_unread_count('fan')
        
        return message

    @classmethod
    def create_tip_message(cls, conversation, sender, tip_amount):
        """Create a tip message"""
        return cls.create_message(
            conversation=conversation,
            sender=sender,
            body=f"Sent a tip of ${tip_amount}",
            message_type=MessageType.TIP,
            tip_amount=tip_amount
        )

    @classmethod
    def get_conversation_messages(cls, conversation, limit=50, before=None):
        """Get messages in a conversation"""
        queryset = cls.objects.filter(conversation=conversation)
        
        if before:
            queryset = queryset.filter(sent_at__lt=before)
        
        return queryset.order_by('-sent_at')[:limit]

    @classmethod
    def get_unread_messages(cls, user):
        """Get unread messages for user"""
        # Check if user is a creator (simplified - in production would check user role)
        is_creator = hasattr(user, 'creator_profile') or user.role == 'creator'
        
        if is_creator:
            # User is a creator
            return cls.objects.filter(
                conversation__creator=user,
                conversation__creator_unread_count__gt=0,
                status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]
            ).exclude(sender=user).order_by('-sent_at')
        else:
            # User is a fan
            return cls.objects.filter(
                conversation__fan=user,
                conversation__fan_unread_count__gt=0,
                status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]
            ).exclude(sender=user).order_by('-sent_at')

    @classmethod
    def mark_conversation_read(cls, conversation, user):
        """Mark all messages in conversation as read for user"""
        if user == conversation.fan:
            messages = cls.objects.filter(
                conversation=conversation,
                status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]
            ).exclude(sender=user)
            conversation.reset_unread_count('fan')
        elif user == conversation.creator:
            messages = cls.objects.filter(
                conversation=conversation,
                status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]
            ).exclude(sender=user)
            conversation.reset_unread_count('creator')
        else:
            return 0
        
        from django.utils import timezone
        count = messages.count()
        messages.update(status=MessageStatus.READ, read_at=timezone.now())
        
        return count

    @classmethod
    def get_message_stats(cls, user, days=30):
        """Get message statistics for user"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Sent messages
        sent_stats = cls.objects.filter(
            sender=user,
            sent_at__gte=cutoff_date
        ).aggregate(
            total=Count('id'),
            text=Count('id', filter=models.Q(message_type=MessageType.TEXT)),
            image=Count('id', filter=models.Q(message_type=MessageType.IMAGE)),
            video=Count('id', filter=models.Q(message_type=MessageType.VIDEO)),
            audio=Count('id', filter=models.Q(message_type=MessageType.AUDIO)),
            file=Count('id', filter=models.Q(message_type=MessageType.FILE)),
            tip=Count('id', filter=models.Q(message_type=MessageType.TIP)),
            automated=Count('id', filter=models.Q(is_automated=True))
        )
        
        # Received messages
        # Check if user is a creator (simplified - in production would check user role)
        is_creator = hasattr(user, 'creator_profile') or user.role == 'creator'
        
        if is_creator:
            # User is a creator
            received_stats = cls.objects.filter(
                conversation__creator=user,
                sent_at__gte=cutoff_date
            ).exclude(sender=user).aggregate(
                total=Count('id'),
                unread=Count('id', filter=models.Q(status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]))
            )
        else:
            # User is a fan
            received_stats = cls.objects.filter(
                conversation__fan=user,
                sent_at__gte=cutoff_date
            ).exclude(sender=user).aggregate(
                total=Count('id'),
                unread=Count('id', filter=models.Q(status__in=[MessageStatus.SENT, MessageStatus.DELIVERED]))
            )
        
        return {
            'sent': sent_stats,
            'received': received_stats,
            'period_days': days
        }
