import uuid
from django.db import models
from .course import Course

class CourseAnnouncement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="announcements")
    instructor = models.ForeignKey("lms_identity.InstructorProfile", on_delete=models.CASCADE)
    
    title = models.CharField(max_length=255)
    body = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_course_announcements"
        app_label = "lms_content"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.course.title}"
