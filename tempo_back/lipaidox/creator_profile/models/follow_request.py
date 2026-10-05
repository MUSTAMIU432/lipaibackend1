import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class FollowRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"


class FollowRequest(TenantAwareModel):
    """A request to follow a private account (``User.requires_follow_approval``).

    Accepting creates the ``Follow`` row. A declined request stays on file so the
    requester can't re-spam: asking again simply puts it back to pending once.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="follow_requests_sent")
    target = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="follow_requests_received")
    status = models.CharField(max_length=10, choices=FollowRequestStatus.choices, default=FollowRequestStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "follow_requests"
        app_label = "lipaidox_creator_profile"
        constraints = [
            models.UniqueConstraint(fields=["requester", "target", "tenant"], name="unique_follow_request_per_tenant"),
        ]
        indexes = [models.Index(fields=["target", "status"])]

    def __str__(self):
        return f"{self.requester} -> {self.target} ({self.status})"
