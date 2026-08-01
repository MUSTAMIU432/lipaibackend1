"""
Middleware to enforce role-based access control at the request level.
Provides additional security layer for API endpoints.
"""

from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from .permissions import UserRoles


class RoleBasedAccessMiddleware:
    """
    Middleware to add role information to request and perform basic role validation.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add role information to request for easy access
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.user_role = getattr(request.user, 'role', UserRoles.FAN)
        else:
            request.user_role = None
        
        response = self.get_response(request)
        return response


def require_role_view(allowed_roles):
    """
    Decorator for Django views to require specific roles.
    Usage:
        @require_role_view([UserRoles.CREATOR, UserRoles.ADMIN])
        def my_view(request):
            # View logic
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            user_role = getattr(request.user, 'role', UserRoles.FAN)
            if user_role not in allowed_roles:
                return JsonResponse({'error': f'Access denied. Required roles: {", ".join(allowed_roles)}'}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_creator_view(view_func):
    """Shortcut decorator for creator-only views."""
    return require_role_view([UserRoles.CREATOR])(view_func)


def require_admin_view(view_func):
    """Shortcut decorator for admin-only views."""
    return require_role_view([UserRoles.ADMIN])(view_func)


def require_creator_or_admin_view(view_func):
    """Shortcut decorator for creator or admin views."""
    return require_role_view([UserRoles.CREATOR, UserRoles.ADMIN])(view_func)
