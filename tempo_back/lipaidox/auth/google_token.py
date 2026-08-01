"""
Backward-compatible re-export. Prefer ``lipaidox.auth.googleauth`` or ``lipaidox.auth.googleOuth``.
"""

from .googleauth import verify_google_credential_jwt

__all__ = ["verify_google_credential_jwt"]
