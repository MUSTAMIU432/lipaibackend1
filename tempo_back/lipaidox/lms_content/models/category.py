import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class CourseCategory(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    icon = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    order_index = models.IntegerField(default=0)

    class Meta:
        db_table = "lms_course_categories"
        app_label = "lms_content"
        verbose_name_plural = "Course Categories"

    def __str__(self):
        return self.name
