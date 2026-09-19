import uuid

from django.db import models


class AppFeedback(models.Model):
    """A star rating (and optional comment) a user gave the app from Settings → Rate the app."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='app_feedback'
    )
    rating = models.PositiveSmallIntegerField()
    message = models.TextField(blank=True, default='')
    app_version = models.CharField(max_length=30, blank=True, default='')
    platform = models.CharField(max_length=40, blank=True, default='')
    app_id = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'app_feedback'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['rating'], name='idx_app_feedback_rating'),
            models.Index(fields=['user', '-created_at'], name='idx_app_feedback_user'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(rating__gte=1, rating__lte=5), name='app_feedback_rating_1_5'),
        ]

    def __str__(self):
        return f"{self.rating}★ — {self.message[:40]}"
