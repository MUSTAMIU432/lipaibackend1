import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .content import Content


class ContentCommentStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"
    FLAGGED = "flagged", "Flagged"


class ContentComment(TenantAwareModel):
    """A viewer's comment on a piece of Content (feed feedback thread).

    Unlike ContentReview there is no rating and no one-per-user constraint —
    viewers can comment as many times as they like.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_comments"
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="comments")
    # A reply points at its top-level parent comment. Threads are two levels deep
    # (comment → replies), YouTube-style: a "reply to a reply" is re-parented to
    # the same top-level comment so the tree never nests further. Null = top level.
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=ContentCommentStatus.choices, default=ContentCommentStatus.PUBLISHED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "content_comments"
        app_label = "lipaidox_content"
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["author"]),
            models.Index(fields=["status"]),
            models.Index(fields=["content", "status", "created_at"]),
            models.Index(fields=["parent", "status", "created_at"]),
        ]

    def __str__(self):
        return f"ContentComment {self.author} -> {self.content_id}"
