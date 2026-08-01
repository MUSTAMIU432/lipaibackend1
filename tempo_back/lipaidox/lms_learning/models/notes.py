import uuid
from django.db import models
from .enrollment import Enrollment

class Note(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="notes")
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE)
    
    content = models.TextField()
    timestamp_seconds = models.IntegerField(default=0) # Bookmark in video
    is_private = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_lesson_notes"
        app_label = "lms_learning"
        ordering = ['-created_at']
