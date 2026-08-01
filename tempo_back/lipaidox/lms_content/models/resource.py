import uuid
from django.db import models
from .lesson import Lesson

class ResourceType(models.TextChoices):
    PDF = 'pdf', 'PDF Document'
    LINK = 'link', 'External Link'
    CODE = 'code', 'Source Code'
    ZIP = 'zip', 'Archive'

class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices, default=ResourceType.PDF)
    url = models.URLField(max_length=500)
    file_size_kb = models.IntegerField(default=0)
    
    class Meta:
        db_table = "lms_resources"
        app_label = "lms_content"

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
