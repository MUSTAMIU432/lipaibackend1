import uuid
from django.db import models
from .lesson import Lesson

class LabType(models.TextChoices):
    CODE = 'code', 'Interactive Code'
    SANDBOX = 'sandbox', 'Sandbox Environment'
    QUIZ = 'quiz', 'Advanced Quiz'

class Lab(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="labs")
    title = models.CharField(max_length=255)
    lab_type = models.CharField(max_length=20, choices=LabType.choices, default=LabType.CODE)
    
    instructions = models.TextField()
    starter_code = models.TextField(null=True, blank=True)
    solution_code = models.TextField(null=True, blank=True)
    
    language = models.CharField(max_length=50, default="python")
    time_limit_mins = models.IntegerField(default=30)
    
    class Meta:
        db_table = "lms_labs"
        app_label = "lms_content"

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
