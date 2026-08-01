import strawberry
from typing import Optional, List
from datetime import datetime, date
from ..models import User

@strawberry.type
class UserType:
    id: strawberry.ID
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone_number: Optional[str]
    phone_country_code: Optional[str]
    date_of_birth: Optional[date]
    role: str
    module: Optional[str]
    isFirstLogin: bool
    staffCapabilities: List[str]
    profileTitle: Optional[str]
    status: str
    email_verified: bool
    phone_verified: bool
    auth_provider: str
    google_id: Optional[str]
    apple_id: Optional[str]
    has_usable_password: bool
    updated_at: datetime

    @classmethod
    def from_model(cls, instance: User):
        return cls(
            id=strawberry.ID(str(instance.id)),
            username=instance.username,
            email=instance.email,
            first_name=instance.first_name or None,
            last_name=instance.last_name or None,
            phone_number=instance.phone_number,
            phone_country_code=instance.phone_country_code,
            date_of_birth=instance.date_of_birth,
            role=instance.role,
            module=instance.module or None,
            isFirstLogin=instance.is_first_login,
            staffCapabilities=instance.staff_capabilities or [],
            profileTitle=instance.profile_title or None,
            status=instance.status,
            email_verified=instance.email_verified,
            phone_verified=instance.phone_verified,
            auth_provider=instance.auth_provider,
            google_id=instance.google_id,
            apple_id=instance.apple_id,
            has_usable_password=instance.has_usable_password(),
            updated_at=instance.updated_at,
        )

@strawberry.input
class UserInput:
    username: str
    email: str
    password: str
    role: Optional[str] = "fan"

@strawberry.input
class UserUpdateInput:
    email: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None

@strawberry.input
class UserSelfUpdateInput:
    """Input for users updating their own account info (non-admin)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    phone_country_code: Optional[str] = None
    date_of_birth: Optional[date] = None
