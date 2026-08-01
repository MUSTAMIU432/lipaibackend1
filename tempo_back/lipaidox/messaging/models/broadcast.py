import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class BroadcastTarget(models.TextChoices):
    ALL_USERS = 'all_users', 'All Users'
    FANS_ONLY = 'fans_only', 'Fans Only'
    CREATORS_ONLY = 'creators_only', 'Creators Only'
    MY_SUBSCRIBERS = 'my_subscribers', 'My Subscribers'
    MY_PPV_BUYERS = 'my_ppv_buyers', 'My PPV Buyers'

class BroadcastMessage(TenantAwareModel):
    """
    Mass messaging from Admin to users, or Creator to their specific fans.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='broadcasts_sent'
    )
    target_audience = models.CharField(max_length=20, choices=BroadcastTarget.choices)
    text = models.TextField()
    
    # Execution
    is_processed = models.BooleanField(default=False)
    total_delivered = models.IntegerField(default=0)
    
    scheduled_for = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'messaging_broadcasts'
        app_label = 'lipaidox_messaging'

    def __str__(self):
        return f"Broadcast to {self.target_audience} by {self.sender.username}"
