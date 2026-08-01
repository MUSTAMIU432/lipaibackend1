import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class AutoDMTrigger(models.TextChoices):
    """Auto DM trigger types"""
    NEW_FOLLOWER = 'new_follower', 'New Follower'
    NEW_SUBSCRIBER = 'new_subscriber', 'New Subscriber'
    NEW_PPV_PURCHASE = 'new_ppv_purchase', 'New PPV Purchase'
    NEW_TIP = 'new_tip', 'New Tip'


class AutoDMRule(TenantAwareModel):
    """
    Auto DM Rules - Module 20
    Automated message rules for creators
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='auto_dm_rules'
    )
    trigger = models.CharField(
        max_length=20,
        choices=AutoDMTrigger.choices
    )
    is_active = models.BooleanField(default=True)
    message_template = models.TextField()
    include_creator_name = models.BooleanField(default=True)
    include_fan_name = models.BooleanField(default=True)
    delay_minutes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auto_dm_rules'
        app_label = 'lipaidox_messaging'
        indexes = [
            models.Index(fields=['creator'], name='idx_auto_dm_rules_creator_id'),
            models.Index(fields=['trigger'], name='idx_auto_dm_rules_trigger'),
            models.Index(fields=['is_active'], name='idx_auto_dm_rules_is_active'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['creator', 'trigger'],
                name='auto_dm_rules_unique'
            ),
            models.CheckConstraint(
                check=models.Q(delay_minutes__gte=0),
                name='delay_check'
            ),
        ]

    def __str__(self):
        return f"Auto DM Rule: {self.creator.username} - {self.trigger}"

    def render_message(self, context):
        """Render message template with context"""
        try:
            # Simple string formatting with template variables
            # Available variables: {fan_name}, {creator_name}, {content_title}, {tip_amount}
            return self.message_template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    @classmethod
    def get_active_rules(cls, creator, trigger=None):
        """Get active auto DM rules for creator"""
        queryset = cls.objects.filter(
            creator=creator,
            is_active=True
        )
        
        if trigger:
            queryset = queryset.filter(trigger=trigger)
        
        return queryset

    @classmethod
    def process_trigger(cls, creator, fan, trigger, context=None):
        """Process auto DM trigger"""
        rules = cls.get_active_rules(creator, trigger)
        
        sent_messages = []
        for rule in rules:
            # Build context for template rendering
            template_context = {
                'fan_name': fan.username,
                'creator_name': creator.username,
            }
            
            # Add trigger-specific context
            if context:
                template_context.update(context)
            
            # Render message
            message_content = rule.render_message(template_context)
            
            # Create conversation if it doesn't exist
            from .conversation import Conversation
            conversation, _ = Conversation.get_or_create_conversation(fan, creator)
            
            # Create message with delay
            if rule.delay_minutes > 0:
                # In production, this would be handled by a background task
                from datetime import timedelta
                from django.utils import timezone
                scheduled_time = timezone.now() + timedelta(minutes=rule.delay_minutes)
                # TODO: Schedule background task
            else:
                # Send immediately
                from .message import Message, MessageType
                message = Message.create_message(
                    conversation=conversation,
                    sender=creator,
                    body=message_content,
                    message_type=MessageType.AUTOMATED,
                    auto_dm_rule=rule
                )
                sent_messages.append(message)
        
        return sent_messages
