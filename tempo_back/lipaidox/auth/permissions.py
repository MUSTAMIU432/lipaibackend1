"""
Role-based access control utilities for Lipaidox platform.
Provides decorators and permission classes for different user roles.
"""

import functools
import strawberry
from typing import Callable, Any
from django.core.exceptions import PermissionDenied
from .models import User


class UserRoles:
    FAN = "fan"
    CREATOR = "creator"
    ADMIN = "admin"


def get_user_role(user) -> str:
    """Get the role of a user, defaulting to 'fan' if not set."""
    if not user or not user.is_authenticated:
        raise Exception("Authentication required. Please log in and try again.")
    return getattr(user, 'role', UserRoles.FAN)


def _extract_request(info) -> Any:
    """
    Extract the Django HttpRequest from a Strawberry Info object.

    Strawberry's context can be:
      - An object with a .request attribute  (dataclass / StrawberryDjangoContext)
      - A plain dict  {"request": <HttpRequest>, ...}
    Both shapes are handled here.
    """
    ctx = info.context
    if hasattr(ctx, 'request'):
        return ctx.request
    if isinstance(ctx, dict) and 'request' in ctx:
        return ctx['request']
    raise Exception("Invalid request context: cannot locate Django request object.")


def _find_info(args, kwargs) -> Any:
    """
    Locate the Strawberry Info object in a resolver call.

    Strawberry (via graphql-core-3) may pass `info` as:
      - a positional argument: wrapper(root, info, ...)
      - a keyword argument:   wrapper(root, info=info_obj, ...)
      - the explicit kwarg name 'info' when signature inspection is used

    We check kwargs['info'] first (most reliable), then scan positional args
    for any object that carries a `.context` attribute.
    """
    # 1. Named kwarg — most reliable across Strawberry versions
    if 'info' in kwargs and hasattr(kwargs['info'], 'context'):
        return kwargs['info']

    # 2. Positional args — root value is first (often None), info is next
    for arg in args:
        if hasattr(arg, 'context'):
            return arg

    # 3. Any kwarg with a context attr (fallback)
    for val in kwargs.values():
        if hasattr(val, 'context'):
            return val

    raise Exception(
        "Authentication check failed: could not locate the request context. "
        "Ensure you are authenticated and your token is valid."
    )


def require_role(required_role: str):
    """
    Decorator to require a specific user role for GraphQL resolvers.

    Usage:
        @strawberry.mutation
        @require_role(UserRoles.CREATOR)
        def my_creator_mutation(self, info: strawberry.types.Info) -> SomeType: ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            info = _find_info(args, kwargs)
            request = _extract_request(info)
            user_role = get_user_role(request.user)

            if user_role != required_role:
                raise Exception(
                    f"{required_role.title()} access required. "
                    f"Your current role is '{user_role}'."
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_role(*allowed_roles: str):
    """
    Decorator to require any of the specified user roles.

    Usage:
        @strawberry.mutation
        @require_any_role(UserRoles.CREATOR, UserRoles.ADMIN)
        def creator_or_admin_mutation(self, info: strawberry.types.Info) -> SomeType: ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            info = _find_info(args, kwargs)
            request = _extract_request(info)
            user_role = get_user_role(request.user)

            if user_role not in allowed_roles:
                role_names = [r.title() for r in allowed_roles]
                raise Exception(
                    f"{' or '.join(role_names)} access required. "
                    f"Your current role is '{user_role}'."
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_creator(func: Callable) -> Callable:
    """Shortcut decorator for creator-only access."""
    return require_role(UserRoles.CREATOR)(func)


def require_admin(func: Callable) -> Callable:
    """Shortcut decorator for admin-only access."""
    return require_role(UserRoles.ADMIN)(func)


def require_creator_or_admin(func: Callable) -> Callable:
    """Shortcut decorator for creator or admin access."""
    return require_any_role(UserRoles.CREATOR, UserRoles.ADMIN)(func)


def check_user_permission(user, required_role: str) -> bool:
    """
    Utility function to check if a user has the required role.
    Returns True if user has the role, False otherwise.
    """
    if not user or not user.is_authenticated:
        return False
    
    user_role = getattr(user, 'role', UserRoles.FAN)
    return user_role == required_role


def check_user_any_permission(user, *allowed_roles: str) -> bool:
    """
    Utility function to check if a user has any of the allowed roles.
    Returns True if user has any of the roles, False otherwise.
    """
    if not user or not user.is_authenticated:
        return False
    
    user_role = getattr(user, 'role', UserRoles.FAN)
    return user_role in allowed_roles


class RolePermissions:
    """
    Permission checking utilities for different user roles.
    """
    
    @staticmethod
    def can_access_creator_features(user) -> bool:
        """Check if user can access creator-specific features."""
        return check_user_permission(user, UserRoles.CREATOR)
    
    @staticmethod
    def can_access_admin_features(user) -> bool:
        """Check if user can access admin features."""
        return check_user_permission(user, UserRoles.ADMIN)
    
    @staticmethod
    def can_access_creator_or_admin_features(user) -> bool:
        """Check if user can access creator or admin features."""
        return check_user_any_permission(user, UserRoles.CREATOR, UserRoles.ADMIN)
    
    @staticmethod
    def can_access_fan_features(user) -> bool:
        """Check if user can access fan features (all authenticated users)."""
        return user and user.is_authenticated
    
    @staticmethod
    def can_manage_content(user) -> bool:
        """Check if user can manage content (creator or admin)."""
        return RolePermissions.can_access_creator_or_admin_features(user)
    
    @staticmethod
    def can_manage_payments(user) -> bool:
        """Check if user can manage payment methods (creator only)."""
        return RolePermissions.can_access_creator_features(user)
    
    @staticmethod
    def can_view_analytics(user) -> bool:
        """Check if user can view analytics (creator or admin)."""
        return RolePermissions.can_access_creator_or_admin_features(user)
    
    @staticmethod
    def can_manage_kyc(user) -> bool:
        """Check if user can manage KYC (creator or admin)."""
        return RolePermissions.can_access_creator_or_admin_features(user)
    
    @staticmethod
    def can_manage_subscriptions(user) -> bool:
        """Check if user can manage subscriptions (creator or admin)."""
        return RolePermissions.can_access_creator_or_admin_features(user)
