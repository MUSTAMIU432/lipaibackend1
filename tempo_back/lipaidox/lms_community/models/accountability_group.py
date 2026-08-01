import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class AccountabilityGroup(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE, related_name="accountability_groups", null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    
    max_members = models.IntegerField(default=10)
    streak_threshold_days = models.IntegerField(default=7)
    streak = models.IntegerField(default=0)
    
    is_private = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_accountability_groups"
        app_label = "lms_community"

class MemberRole(models.TextChoices):
    LEADER = 'leader', 'Leader'
    MEMBER = 'member', 'Member'

class AccountabilityMember(models.Model):
    group = models.ForeignKey(AccountabilityGroup, on_delete=models.CASCADE, related_name="members")
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE)
    
    role = models.CharField(max_length=20, choices=MemberRole.choices, default=MemberRole.MEMBER)
    weekly_goal_hours = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    current_week_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    joined_at = models.DateTimeField(auto_now_add=True)
    current_streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    
    class Meta:
        db_table = "lms_accountability_members"
        app_label = "lms_community"
        unique_together = ('group', 'student')

class DailyGoal(models.Model):
    member = models.ForeignKey(AccountabilityMember, on_delete=models.CASCADE, related_name="goals")
    date = models.DateField(auto_now_add=True)
    
    goal_description = models.CharField(max_length=500)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_accountability_daily_goals"
        app_label = "lms_community"
        unique_together = ('member', 'date')
