from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import OtpPurpose, UserRecord


@runtime_checkable
class UserRepository(Protocol):
    def get_by_email_normalized(self, email_normalized: str) -> UserRecord | None:
        ...

    def get_by_id(self, user_id: str) -> UserRecord | None:
        ...

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        ...


@runtime_checkable
class OtpRepository(Protocol):
    def save_otp(
        self,
        *,
        email_normalized: str,
        purpose: OtpPurpose,
        user_id: str,
        code_hash: str,
        expires_in_seconds: int,
    ) -> None:
        ...

    def verify_otp_active(
        self,
        *,
        email_normalized: str,
        purpose: OtpPurpose,
        code_plain: str,
    ) -> bool:
        ...

    def consume_otp(self, *, email_normalized: str, purpose: OtpPurpose) -> None:
        ...


@runtime_checkable
class Mailer(Protocol):
    def send_otp_email(
        self,
        *,
        to_email: str,
        purpose: OtpPurpose,
        code_plain: str,
    ) -> None:
        ...
