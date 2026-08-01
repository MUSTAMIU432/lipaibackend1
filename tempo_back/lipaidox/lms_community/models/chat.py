import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class ChannelType(models.TextChoices):
    TEXT = 'text', 'Text Channel'
    VOICE = 'voice', 'Voice Channel'

class MessageType(models.TextChoices):
    TEXT = 'text', 'Text Message'
    FILE = 'file', 'File Message'
    IMAGE = 'image', 'Image Message'

class StudyRoomChannel(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey("lms_community.StudyRoom", on_delete=models.CASCADE, related_name="channels")
    
    name = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices, default=ChannelType.TEXT)
    description = models.TextField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_study_room_channels"
        app_label = "lms_community"

    def __str__(self):
        return f"{self.name} - {self.room.name}"

class StudyRoomMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(StudyRoomChannel, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="chat_messages")
    
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    is_pinned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_study_room_messages"
        app_label = "lms_community"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} in {self.channel.name}"

class MessageReaction(models.Model):
    message = models.ForeignKey(StudyRoomMessage, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE)
    emoji = models.CharField(max_length=50)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_message_reactions"
        app_label = "lms_community"
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} {self.emoji}"
