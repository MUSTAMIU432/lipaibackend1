import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .content import Content


class ContentView(TenantAwareModel):
    """A unique view of a piece of Content — one per user per content.

    The denormalised `Content.view_count` is incremented only the first time a
    given user opens the content, so the feed's view count reflects distinct
    viewers rather than every re-open. Mirrors ContentLike.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_views"
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="views")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_views"
        app_label = "lipaidox_content"
        constraints = [
            models.UniqueConstraint(fields=["user", "content"], name="unique_view_per_user_content"),
        ]
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"ContentView {self.user} -> {self.content_id}"
