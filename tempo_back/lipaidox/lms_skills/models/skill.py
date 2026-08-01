import uuid
from django.db import models
from .category import SkillCategory

class StudentSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="skills")
    category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name="students")
    
    skill_name = models.CharField(max_length=255)
    proficiency_level = models.IntegerField(default=1) # 1-10 scale
    
    is_verified = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_student_skills"
        app_label = "lms_skills"
        unique_together = ('student', 'skill_name')

    def __str__(self):
        return f"{self.student.user.username} - {self.skill_name} ({self.proficiency_level})"
