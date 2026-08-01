import uuid
from django.conf import settings
from django.db import models
from multitenant.models import TenantAwareModel
from .profile import CreatorProfile


class MembershipStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"


class NotificationPreference(models.TextChoices):
    ALL = "all", "All"
    PERSONALIZED = "personalized", "Personalized"
    NONE = "none", "None"


class MembershipSubscription(TenantAwareModel):
    """
    Free membership/subscription relationship between a fan and a creator.

    Deliberately separate from `lipaidox.subscriptions.Subscription` (which is
    payment-oriented). This model carries NO price/billing fields — every
    membership is free and becomes ACTIVE the moment the row is created.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership_subscriptions"
    )
    target = models.ForeignKey(
        CreatorProfile, on_delete=models.CASCADE, related_name="member_subscriptions"
    )
    status = models.CharField(max_length=20, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE)
    notification_preference = models.CharField(
        max_length=20, choices=NotificationPreference.choices, default=NotificationPreference.PERSONALIZED
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "membership_subscriptions"
        app_label = "lipaidox_creator_profile"
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber", "target", "tenant"], name="unique_membership_per_tenant"
            ),
        ]
        indexes = [
            models.Index(fields=["subscriber"]),
            models.Index(fields=["target"]),
            models.Index(fields=["status"]),
            models.Index(fields=["subscriber", "created_at"]),
            models.Index(fields=["target", "created_at"]),
            models.Index(fields=["subscriber", "target"]),
        ]

    def __str__(self):
        return f"{self.subscriber} -> {self.target} ({self.status})"
