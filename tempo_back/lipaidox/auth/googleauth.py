"""
Sign-in for GraphQL ``googleAuth`` — re-export (Firebase ID tokens + optional GIS JWT).

**Firebase:** Admin verifies Firebase Auth ID tokens (service account / ``authjson``).  
**GIS:** Optional; uses ``GOOGLE_OAUTH_CLIENT_ID``. See :mod:`lipaidox.auth.googleOuth.googleOuth`.
"""

from .googleOuth.googleOuth import (
    FirebaseAuthService,
    normalize_google_id_token,
    peek_google_jwt_issuer,
    verify_google_credential_jwt,
)

__all__ = [
    "FirebaseAuthService",
    "normalize_google_id_token",
    "peek_google_jwt_issuer",
    "verify_google_credential_jwt",
]
