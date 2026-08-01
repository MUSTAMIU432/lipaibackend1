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
    """Returned on register or login — user profile + tokens so the frontend can proceed immediately."""
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
