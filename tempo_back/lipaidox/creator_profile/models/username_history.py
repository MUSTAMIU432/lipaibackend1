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
    """Check if username is available for use"""
    # Debug logging
    print(f"DEBUG is_username_available: username='{username}', tenant='{tenant}', exclude_user='{exclude_user.username if exclude_user else None}'")
    
    # Check if username is currently in use
    query = UsernameHistory.objects.filter(
        username=username,
        tenant=tenant,
        is_available=False
    )
    
    print(f"DEBUG: Base query count: {query.count()}")
    
    if exclude_user:
        query = query.exclude(user=exclude_user)
        print(f"DEBUG: After exclude query count: {query.count()}")
    
    exists = query.exists()
    result = not exists
    print(f"DEBUG: Final result: {result}")
    
    return result
