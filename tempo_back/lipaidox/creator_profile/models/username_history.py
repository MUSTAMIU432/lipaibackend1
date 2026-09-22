import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class UsernameHistory(TenantAwareModel):
    """
    Track username changes to enable username recycling
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, db_index=True)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="username_history")
    changed_at = models.DateTimeField(auto_now_add=True)
    is_available = models.BooleanField(default=True)  # Available for others to use
    
    class Meta:
        db_table = "username_history"
        app_label = "lipaidox_creator_profile"
        constraints = [
            # Ensure username is unique across active profiles
            models.UniqueConstraint(
                fields=['username', 'tenant'], 
                condition=models.Q(is_available=False),
                name='unique_active_username'
            ),
        ]
        indexes = [
            models.Index(fields=['username', 'is_available']),
            models.Index(fields=['user', 'changed_at']),
        ]
    
    def __str__(self):
        return f"{self.username} -> {self.user.username} ({'available' if self.is_available else 'in use'})"


def reserve_username(username, user, tenant):
    """Mark username as unavailable when claimed by a user"""
    # Mark any existing history for this username as unavailable
    UsernameHistory.objects.filter(
        username=username, 
        tenant=tenant,
        is_available=True
    ).update(is_available=False)
    
    # Create new history entry
    return UsernameHistory.objects.create(
        username=username,
        user=user,
        tenant=tenant,
        is_available=False
    )


def release_username(username, tenant):
    """Release username back to available pool"""
    UsernameHistory.objects.filter(
        username=username,
        tenant=tenant,
        is_available=False
    ).update(is_available=True)


def is_username_available(username, tenant, exclude_user=None):
    """Check if username is available for use.

    Two independent things can make a username unavailable, and both are
    checked: it's the *current* username of some other account (the actual
    unique columns on `User`/`CreatorProfile` — not every signup path calls
    `reserve_username`, so `UsernameHistory` alone used to miss these and
    call a genuinely-taken name "available"), or it was recently released by
    someone else and is still cooling down in `UsernameHistory`.
    """
    from lipaidox.auth.models import User
    from .profile import CreatorProfile

    user_qs = User.objects.filter(username__iexact=username, tenant=tenant)
    profile_qs = CreatorProfile.objects.filter(username__iexact=username, tenant=tenant)
    if exclude_user:
        user_qs = user_qs.exclude(id=exclude_user.id)
        profile_qs = profile_qs.exclude(user=exclude_user)
    if user_qs.exists() or profile_qs.exists():
        return False

    # Check the recycling ledger for anyone still holding a claim on it.
    history_qs = UsernameHistory.objects.filter(
        username=username,
        tenant=tenant,
        is_available=False,
    )
    if exclude_user:
        history_qs = history_qs.exclude(user=exclude_user)

    return not history_qs.exists()
