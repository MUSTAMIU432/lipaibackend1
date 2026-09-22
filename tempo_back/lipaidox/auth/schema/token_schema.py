import strawberry
from typing import Optional
from datetime import datetime
from ..models import RefreshToken


@strawberry.type
class RefreshTokenType:
    id: strawberry.ID
    token_hash: str
    status: str
    device_name: Optional[str]
    last_used_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, instance: RefreshToken):
        return cls(
            id=strawberry.ID(str(instance.id)),
            token_hash=instance.token_hash,
            status=instance.status,
            device_name=instance.device_name,
            last_used_at=instance.last_used_at,
            expires_at=instance.expires_at,
            created_at=instance.created_at,
        )


@strawberry.type
class AuthTokenType:
    """Returned on successful login — contains JWT access token and opaque refresh token."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds until access token expires


@strawberry.type
class AuthPayload:
    """Returned on register or login — user profile + tokens so the frontend can proceed immediately.

    When the account has 2FA enabled, `loginUser` returns this with
    `requires_two_factor=True`, `challenge_token` set, and every token
    field blank rather than real credentials — nothing usable to
    authenticate with until `completeTwoFactorLogin` exchanges the
    challenge + a correct code for a second, real `AuthPayload`.
    """
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user_id: strawberry.ID
    username: str
    email: str
    role: str
    first_name: str = ""
    last_name: str = ""
    requires_two_factor: bool = False
    challenge_token: Optional[str] = None
