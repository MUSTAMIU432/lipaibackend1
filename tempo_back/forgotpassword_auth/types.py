from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class OtpPurpose(str, Enum):
    """Stored with the OTP so verify/apply steps stay unambiguous."""

    FORGOT_PASSWORD = "forgot_password"
    INITIAL_PASSWORD = "initial_password"


@dataclass
class ServiceResult(Generic[T]):
    success: bool
    data: Optional[T] = None
    error_code: Optional[str] = None
    message: Optional[str] = None

    @staticmethod
    def ok(data: Optional[T] = None) -> "ServiceResult[T]":
        return ServiceResult(success=True, data=data)

    @staticmethod
    def fail(code: str, message: str) -> "ServiceResult[T]":
        return ServiceResult(success=False, error_code=code, message=message)


@dataclass
class UserRecord:
    """Minimal user view required by this package."""

    id: str
    email: str
    email_normalized: str
    has_password: bool
    is_google_linked: bool
    may_request_password_reset: bool
    metadata: dict[str, Any]
