import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class MoodType(models.TextChoices):
    GREAT = 'great', 'Great'
    GOOD = 'good', 'Good'
    OKAY = 'okay', 'Okay'
    STRUGGLING = 'struggling', 'Struggling'

class AccountabilityCheckIn(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey("lms_community.AccountabilityGroup", on_delete=models.CASCADE, related_name="check_ins")
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="accountability_check_ins")
    
    content = models.TextField()
    hours_logged = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    mood = models.CharField(max_length=20, choices=MoodType.choices, default=MoodType.GOOD)
    
    achievements = models.JSONField(default=list)  # List of achievements
    blockers = models.JSONField(default=list)  # List of blockers/challenges
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_accountability_check_ins"
        app_label = "lms_community"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} check-in - {self.group.name}"
