"""
JWT helpers for the GraphQL layer.
Uses PyJWT directly (already installed).
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta, timezone

from django.conf import settings


ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_LIFETIME = timedelta(days=30)
ALGORITHM = "HS256"


# ─── Token Generation ─────────────────────────────────────────────────────────

def generate_access_token(user) -> str:
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "exp": datetime.now(tz=timezone.utc) + ACCESS_TOKEN_LIFETIME,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    """Returns a raw UUID-like opaque token (stored hashed in DB)."""
    return secrets.token_hex(40)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


# ─── Token Verification ────────────────────────────────────────────────────────

def verify_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ─── Request Authentication ───────────────────────────────────────────────────

def authenticate_request(request) -> None:
    """
    Reads Bearer token from the Authorization header and sets request.user.
    Called by JWTGraphQLView before Strawberry processes the request.
    """
    from lipaidox.auth.models import User  # local import to avoid circular

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return

    token = auth_header.split(" ", 1)[1]
    payload = verify_access_token(token)
    if not payload:
        return

    try:
        request.user = User.objects.get(id=payload["user_id"])
    except User.DoesNotExist:
        pass
