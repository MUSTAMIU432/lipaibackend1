import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class BadgeType(models.TextChoices):
    PLATINUM = 'platinum', 'Platinum'
    GOLD = 'gold', 'Gold'
    SILVER = 'silver', 'Silver'
    BRONZE = 'bronze', 'Bronze'

class SkillBadge(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="badges")
    
    skill_name = models.CharField(max_length=255)
    badge_type = models.CharField(max_length=20, choices=BadgeType.choices, default=BadgeType.BRONZE)
    
    score = models.IntegerField(default=0)
    assessments_count = models.IntegerField(default=0)
    endorsements_count = models.IntegerField(default=0)
    
    earned_at = models.DateTimeField(auto_now_add=True)
    verification_code = models.CharField(max_length=100, unique=True)
    
    class Meta:
        db_table = "lms_skill_badges"
        app_label = "lms_certification"

class BadgeEndorsement(models.Model):
    badge = models.ForeignKey(SkillBadge, on_delete=models.CASCADE, related_name="endorsements")
    endorsed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    endorsed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "lms_badge_endorsements"
        app_label = "lms_certification"
        unique_together = ('badge', 'endorsed_by')
