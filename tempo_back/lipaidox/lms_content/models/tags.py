import uuid
from django.db import models
from .course import Course

class CourseTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "lms_course_tags"
        app_label = "lms_content"
        unique_together = ('course', 'name')

    def __str__(self):
        return f"{self.name} ({self.course.title})"
