import uuid
from django.db import models
from django.conf import settings
from .enrollment import Enrollment

class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey("lms_content.Lesson", on_delete=models.CASCADE, related_name="questions")
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE)
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_resolved = models.BooleanField(default=False)
    upvotes = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_lesson_questions"
        app_label = "lms_learning"

class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    content = models.TextField()
    is_accepted = models.BooleanField(default=False)
    upvotes = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_lesson_answers"
        app_label = "lms_learning"
