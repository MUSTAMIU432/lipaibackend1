import uuid
from django.db import models
from .course import Course
from .section import CourseSection

class LessonType(models.TextChoices):
    VIDEO = 'video', 'Video'
    QUIZ = 'quiz', 'Quiz'
    LAB = 'lab', 'Lab'
    ASSIGNMENT = 'assignment', 'Assignment'
    READING = 'reading', 'Reading'

class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="all_lessons")
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, related_name="lessons")
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    lesson_type = models.CharField(max_length=20, choices=LessonType.choices, default=LessonType.VIDEO)
    
    content_url = models.URLField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    order_index = models.IntegerField(default=0)
    
    is_free_preview = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        db_table = "lms_lessons"
        app_label = "lms_content"
        ordering = ['order_index']
        unique_together = ('course', 'slug')

    def __str__(self):
        return f"{self.section.title} - {self.title}"
