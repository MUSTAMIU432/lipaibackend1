import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .profile import CreatorProfile


class ReviewStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"
    FLAGGED = "flagged", "Flagged"
    REJECTED = "rejected", "Rejected"


class Review(TenantAwareModel):
    """A user's review + rating of a creator (CreatorProfile)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="authored_reviews"
    )
    target = models.ForeignKey(CreatorProfile, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()  # 1..5, validated in the service
    title = models.CharField(max_length=120, blank=True, default="")
    body = models.TextField()
    status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PUBLISHED)
    is_verified = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    edited_at = models.DateTimeField(null=True, blank=True)
    # Single public reply from the reviewed creator (Play-Store style "developer response").
    owner_reply = models.TextField(blank=True, default="")
    owner_replied_at = models.DateTimeField(null=True, blank=True)
    owner_reply_edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "creator_reviews"
        app_label = "lipaidox_creator_profile"
        constraints = [
            models.UniqueConstraint(fields=["author", "target", "tenant"], name="unique_review_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["target"]),
            models.Index(fields=["author"]),
            models.Index(fields=["status"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["target", "status", "created_at"]),
        ]

    def __str__(self):
        return f"Review({self.rating}★) {self.author} -> {self.target}"


class ReviewHelpful(TenantAwareModel):
    """One helpful mark per user per review (idempotent)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="helpful_marks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_helpful_marks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_helpful_marks"
        app_label = "lipaidox_creator_profile"
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="unique_review_helpful"),
        ]
        indexes = [models.Index(fields=["review"]), models.Index(fields=["user"])]


class ReviewReport(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_reports")
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_reports"
        app_label = "lipaidox_creator_profile"
        indexes = [models.Index(fields=["review"])]
