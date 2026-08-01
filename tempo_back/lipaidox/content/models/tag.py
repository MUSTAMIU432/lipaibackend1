import uuid
from django.db import models
from .content import Content

class ContentTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="tags_list")
    tag = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_tags"
        app_label = "lipaidox_content"
        unique_together = ('content', 'tag')

    def __str__(self):
        return f"#{self.tag} for {self.content.title}"
