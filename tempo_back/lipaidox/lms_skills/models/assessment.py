import uuid
from django.db import models
from .skill import StudentSkill

class SkillAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_skill = models.ForeignKey(StudentSkill, on_delete=models.CASCADE, related_name="assessments")
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE)
    
    score = models.IntegerField(default=0)
    max_score = models.IntegerField(default=100)
    passed = models.BooleanField(default=False)
    
    taken_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata for the assessment attempt (e.g., quiz ID if connected)
    assessment_metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = "lms_skill_assessments"
        app_label = "lms_skills"
        ordering = ['-taken_at']

    def __str__(self):
        return f"{self.student.user.username} - {self.student_skill.skill_name} - {self.score}"
