"""
Google OAuth (GIS JWT) + optional Firebase Admin — all configuration via Django settings / `.env`.

Use `verify_google_credential_jwt` for GraphQL `googleAuth`.
"""

from .googleOuth import (
    FirebaseAuthService,
    FirebaseTokenError,
    firebase_google_identity,
    firebase_sign_in_provider,
    normalize_google_id_token,
    peek_google_jwt_issuer,
    verify_google_credential_jwt,
)

__all__ = [
    "FirebaseAuthService",
    "FirebaseTokenError",
    "firebase_google_identity",
    "firebase_sign_in_provider",
    "normalize_google_id_token",
    "peek_google_jwt_issuer",
    "verify_google_credential_jwt",
]
