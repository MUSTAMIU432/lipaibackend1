"""
Account state rules for login, signup (duplicate detection), and password reset.
Aligns with User.status and Django's is_active (AbstractUser).
"""

from __future__ import annotations

from .models import User

# Accounts in these states cannot sign in or request password reset.
BLOCKED_ACCOUNT_STATUSES = frozenset(
    {
        "suspended",
        "banned",
        "inactive",
        "deleted",
        "disabled",
    }
)


def find_user_by_email_tenant(email_normalized: str, tenant_id):
    """Case-insensitive email match within a tenant (single row if unique constraint holds)."""
    return (
        User.objects.filter(email__iexact=email_normalized, tenant_id=tenant_id)
        .select_related("tenant")
        .first()
    )


def email_already_registered(email_normalized: str, tenant_id) -> bool:
    return User.objects.filter(
        email__iexact=email_normalized, tenant_id=tenant_id
    ).exists()


def user_account_is_usable(user: User) -> bool:
    """True if the row may authenticate or use self-service password reset."""
    if not getattr(user, "is_active", True):
        return False
    status = (getattr(user, "status", None) or "").strip().lower()
    if status in BLOCKED_ACCOUNT_STATUSES:
        return False
    return True


def assert_user_may_authenticate(user: User) -> None:
    """After password check succeeds — enforce active account policy."""
    if not getattr(user, "is_active", True):
        raise Exception(
            "This account is deactivated. Contact support if you need help."
        )
    status = (getattr(user, "status", None) or "").strip().lower()
    if status in BLOCKED_ACCOUNT_STATUSES:
        raise Exception(
            "This account is not active. Contact support if you need help."
        )


def assert_user_may_request_password_reset(user: User) -> None:
    """Same policy as login for reset eligibility (user must exist for tenant)."""
    assert_user_may_authenticate(user)
