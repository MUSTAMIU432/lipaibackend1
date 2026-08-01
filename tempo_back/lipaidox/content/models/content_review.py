import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .content import Content


class ContentReviewStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"
    FLAGGED = "flagged", "Flagged"
    REJECTED = "rejected", "Rejected"


class ContentReview(TenantAwareModel):
    """A viewer's review + rating of a specific piece of Content (video/post)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_reviews"
    )
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # 1..5, validated in the service
    title = models.CharField(max_length=120, blank=True, default="")
    body = models.TextField()
    status = models.CharField(max_length=20, choices=ContentReviewStatus.choices, default=ContentReviewStatus.PUBLISHED)
    is_verified = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    edited_at = models.DateTimeField(null=True, blank=True)
    # Single public reply from the content owner (Play-Store style "developer response").
    owner_reply = models.TextField(blank=True, default="")
    owner_replied_at = models.DateTimeField(null=True, blank=True)
    owner_reply_edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "content_reviews"
        app_label = "lipaidox_content"
        constraints = [
            models.UniqueConstraint(fields=["author", "content", "tenant"], name="unique_content_review_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["author"]),
            models.Index(fields=["status"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["content", "status", "created_at"]),
        ]

    def __str__(self):
        return f"ContentReview({self.rating}★) {self.author} -> {self.content_id}"


class ContentReviewHelpful(TenantAwareModel):
    """One helpful mark per user per content review (idempotent)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(ContentReview, on_delete=models.CASCADE, related_name="helpful_marks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_review_helpful_marks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_review_helpful_marks"
        app_label = "lipaidox_content"
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="unique_content_review_helpful"),
        ]
        indexes = [models.Index(fields=["review"]), models.Index(fields=["user"])]
