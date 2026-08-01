import uuid
from django.db import models
from .course import Course

class CourseSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=255)
    order_index = models.IntegerField(default=0)
    
    class Meta:
        db_table = "lms_course_sections"
        app_label = "lms_content"
        ordering = ['order_index']

    def __str__(self):
        return f"{self.course.title} - {self.title}"
