import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .content import Content


class ContentLike(TenantAwareModel):
    """A viewer's like on a piece of Content — one per user per content.

    The denormalised `Content.like_count` is kept in step by the like/unlike
    mutations, so the feed's count reflects real likes rather than an
    ever-growing interaction log.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_likes"
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_likes"
        app_label = "lipaidox_content"
        constraints = [
            models.UniqueConstraint(fields=["user", "content"], name="unique_like_per_user_content"),
        ]
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"ContentLike {self.user} -> {self.content_id}"
