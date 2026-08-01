import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class MessageType(models.TextChoices):
    TEXT = 'text', 'Text'
    FILE = 'file', 'File'

class Message(TenantAwareModel):
    """
    Messages in educational conversations
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "lipaidox.Tenant",
        on_delete=models.CASCADE,
        related_name="lms_message_instances"
    )
    
    # Conversation relationship
    conversation = models.ForeignKey(
        "Conversation",
        on_delete=models.CASCADE,
        related_name="messages"
    )
    
    # Sender
    sender = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="lms_messages"
    )
    
    # Content
    content = models.TextField()
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )
    
    # Read status
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_messages"
        app_label = "lms_messages"
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['conversation'], name='idx_msg_conversation'),
            models.Index(fields=['sender'], name='idx_msg_sender'),
            models.Index(fields=['-sent_at'], name='idx_msg_sent_at'),
            models.Index(fields=['read_at'], name='idx_msg_read_at'),
        ]
    
    def __str__(self):
        return f"Message: {self.sender.username} in {self.conversation.course.title}"
    
    def mark_as_read(self):
        """Mark message as read"""
        from django.utils import timezone
        if not self.read_at:
            self.read_at = timezone.now()
            self.save()
    
    def can_view(self, user):
        """Check if user can view this message"""
        return self.conversation.can_participate(user)
    
    @classmethod
    def create_message(cls, conversation, sender, content, message_type=MessageType.TEXT):
        """Create a new message"""
        message = cls.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            message_type=message_type,
            tenant=conversation.tenant
        )
        
        # Update conversation's last message time
        conversation.last_message_at = message.sent_at
        conversation.save()
        
        return message
    
    @classmethod
    def get_conversation_messages(cls, conversation, limit=50):
        """Get messages in a conversation"""
        return cls.objects.filter(conversation=conversation).order_by('sent_at')[:limit]
    
    @classmethod
    def get_unread_count(cls, conversation, user):
        """Get unread message count for user in conversation"""
        return cls.objects.filter(
            conversation=conversation,
            read_at__isnull=True
        ).exclude(sender=user).count()
    
    @classmethod
    def mark_conversation_read(cls, conversation, user):
        """Mark all messages in conversation as read for user"""
        from django.utils import timezone
        unread_messages = cls.objects.filter(
            conversation=conversation,
            read_at__isnull=True
        ).exclude(sender=user)
        
        count = unread_messages.count()
        unread_messages.update(read_at=timezone.now())
        
        return count
