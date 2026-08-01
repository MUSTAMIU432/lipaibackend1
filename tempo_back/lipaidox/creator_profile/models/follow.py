import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class Follow(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="following_set")
    followed = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="followers_set")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follows"
        app_label = "lipaidox_creator_profile"
        constraints = [
            models.UniqueConstraint(fields=["follower", "followed", "tenant"], name="unique_follow_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["followed"]),
        ]

    def __str__(self):
        return f"{self.follower} -> {self.followed}"
