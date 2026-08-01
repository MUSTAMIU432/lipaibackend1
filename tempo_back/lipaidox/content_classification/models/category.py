import uuid
from django.db import models

class PlatformCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_categories"
        app_label = "lipaidox_cc"
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name
