import uuid
from django.db import models
from django.utils import timezone
from multitenant.models import TenantAwareModel


class ConversationType(models.TextChoices):
    """Conversation types"""
    FAN_TO_CREATOR = 'fan_to_creator', 'Fan to Creator'
    CREATOR_TO_FAN = 'creator_to_fan', 'Creator to Fan'
    PLATFORM_TO_USER = 'platform_to_user', 'Platform to User'


class ConversationStatus(models.TextChoices):
    """Conversation status"""
    ACTIVE = 'active', 'Active'
    ARCHIVED = 'archived', 'Archived'
    BLOCKED = 'blocked', 'Blocked'
    DELETED = 'deleted', 'Deleted'


class Conversation(TenantAwareModel):
    """
    Conversations - Module 20
    Direct message conversations between fans and creators
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='fan_conversations'
    )
    creator = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='creator_conversations'
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.FAN_TO_CREATOR
    )
    status = models.CharField(
        max_length=15,
        choices=ConversationStatus.choices,
        default=ConversationStatus.ACTIVE
    )

    # Last Message Snapshot
    last_message_id = models.UUIDField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=255, null=True, blank=True)

    # Unread Counts
    fan_unread_count = models.IntegerField(default=0)
    creator_unread_count = models.IntegerField(default=0)

    # Blocking
    blocked_by = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blocked_conversations'
    )
    blocked_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.TextField(null=True, blank=True)

    # Archiving
    archived_by_fan = models.BooleanField(default=False)
    archived_by_creator = models.BooleanField(default=False)

    # Pin / Mute / Hide / Clear (per participant side)
    pinned_by_fan = models.BooleanField(default=False)
    pinned_by_creator = models.BooleanField(default=False)
    muted_by_fan = models.BooleanField(default=False)
    muted_by_creator = models.BooleanField(default=False)
    hidden_by_fan = models.BooleanField(default=False)
    hidden_by_creator = models.BooleanField(default=False)
    cleared_at_fan = models.DateTimeField(null=True, blank=True)
    cleared_at_creator = models.DateTimeField(null=True, blank=True)

    # Locked / secret chats
    is_locked = models.BooleanField(default=False)
    lock_type = models.CharField(max_length=10, null=True, blank=True)   # pin|password
    lock_code = models.CharField(max_length=255, null=True, blank=True)
    secret_name = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Disappearing messages (conversation-level default)
    disappearing_enabled = models.CharField(max_length=10, default='off')  # off|1h|24h|7d|30d|custom
    disappearing_duration_ms = models.BigIntegerField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        app_label = 'lipaidox_messaging'
        indexes = [
            models.Index(fields=['fan'], name='idx_conversations_fan_id'),
            models.Index(fields=['creator'], name='idx_conversations_creator_id'),
            models.Index(fields=['status'], name='idx_conversations_status'),
            models.Index(fields=['-last_message_at'], name='idx_conversations_last_msg_at'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fan', 'creator'],
                name='conversations_unique'
            ),
            models.CheckConstraint(
                check=models.Q(fan_unread_count__gte=0) & models.Q(creator_unread_count__gte=0),
                name='unread_counts_check'
            ),
        ]

    def __str__(self):
        return f"Conversation: {self.fan.username} ↔ {self.creator.username}"

    def is_archived_for_user(self, user):
        """Check if conversation is archived for user"""
        if user == self.fan:
            return self.archived_by_fan
        elif user == self.creator:
            return self.archived_by_creator
        return False

    def archive_for_user(self, user):
        """Archive conversation for user"""
        if user == self.fan:
            self.archived_by_fan = True
        elif user == self.creator:
            self.archived_by_creator = True
        self.save()

    def unarchive_for_user(self, user):
        """Unarchive conversation for user"""
        if user == self.fan:
            self.archived_by_fan = False
        elif user == self.creator:
            self.archived_by_creator = False
        self.save()

    def block_conversation(self, blocked_by, reason=None):
        """Block conversation"""
        self.status = ConversationStatus.BLOCKED
        self.blocked_by = blocked_by
        self.blocked_at = timezone.now()
        self.block_reason = reason
        self.save()

    def unblock_conversation(self):
        """Unblock conversation"""
        self.status = ConversationStatus.ACTIVE
        self.blocked_by = None
        self.blocked_at = None
        self.block_reason = None
        self.save()

    def update_last_message(self, message):
        """Update last message info"""
        self.last_message_id = message.id
        self.last_message_at = message.sent_at
        self.last_message_preview = message.body[:255] if message.body else ""
        self.save()

    def increment_unread_count(self, user_type):
        """Increment unread count for user type"""
        if user_type == 'fan':
            self.fan_unread_count += 1
        elif user_type == 'creator':
            self.creator_unread_count += 1
        self.save()

    def reset_unread_count(self, user_type):
        """Reset unread count for user type"""
        if user_type == 'fan':
            self.fan_unread_count = 0
        elif user_type == 'creator':
            self.creator_unread_count = 0
        self.save()

    @classmethod
    def get_or_create_conversation(cls, fan, creator):
        """Get or create conversation between fan and creator"""
        conversation, created = cls.objects.get_or_create(
            fan=fan,
            creator=creator,
            tenant=fan.tenant,
            defaults={
                'conversation_type': ConversationType.FAN_TO_CREATOR,
                'status': ConversationStatus.ACTIVE
            }
        )
        
        return conversation, created

    @classmethod
    def get_user_conversations(cls, user, include_archived=False):
        """Get user's conversations"""
        # Check if user is a creator (simplified - in production would check user role)
        is_creator = hasattr(user, 'creator_profile') or user.role == 'creator'
        
        if is_creator:
            # User is a creator
            queryset = cls.objects.filter(creator=user)
            if not include_archived:
                queryset = queryset.exclude(archived_by_creator=True)
        else:
            # User is a fan
            queryset = cls.objects.filter(fan=user)
            if not include_archived:
                queryset = queryset.exclude(archived_by_fan=True)
        
        return queryset.order_by('-last_message_at', '-created_at')
