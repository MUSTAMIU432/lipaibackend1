import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class SkillCategory(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    
    # Hierarchical Categories
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name="subcategories")
    
    class Meta:
        db_table = "lms_skill_categories"
        app_label = "lms_skills"

    def __str__(self):
        return self.name
