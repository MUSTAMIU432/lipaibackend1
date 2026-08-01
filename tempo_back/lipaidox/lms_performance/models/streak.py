import uuid
from django.db import models

class LearningStreak(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="learning_streak")
    
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_learning_streaks"
        app_label = "lms_performance"

    def __str__(self):
        return f"{self.student.user.username} - Streak: {self.current_streak}"
