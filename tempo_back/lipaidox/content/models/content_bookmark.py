import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .content import Content


class ContentBookmark(TenantAwareModel):
    """A viewer's saved/bookmarked Content — one per user per content.

    Powers the "Saved posts" surface and the save toggle on feed cards.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_bookmarks"
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_bookmarks"
        app_label = "lipaidox_content"
        constraints = [
            models.UniqueConstraint(fields=["user", "content"], name="unique_bookmark_per_user_content"),
        ]
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["user"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"ContentBookmark {self.user} -> {self.content_id}"
