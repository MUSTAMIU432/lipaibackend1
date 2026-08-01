import uuid
from django.db import models
from .enrollment import Enrollment

class LessonProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE)
    
    watch_time_seconds = models.IntegerField(default=0)
    last_position_seconds = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_lesson_progress"
        app_label = "lms_learning"
        unique_together = ('enrollment', 'lesson')
