from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from forgotpassword_auth.otp_util import hash_otp, normalize_email
from forgotpassword_auth.service import ForgotPasswordAuthService
from forgotpassword_auth.types import OtpPurpose, UserRecord


@dataclass
class _OtpRow:
    user_id: str
    code_hash: str
    expires_in_seconds: int
    consumed: bool = False


class FakeOtpRepository:
    def __init__(self, pepper: str) -> None:
        self._pepper = pepper
        self._rows: Dict[tuple[str, OtpPurpose], _OtpRow] = {}
        self._now_offset = 0

    def save_otp(
        self,
        *,
        email_normalized: str,
        purpose: OtpPurpose,
        user_id: str,
        code_hash: str,
        expires_in_seconds: int,
    ) -> None:
        self._rows[(email_normalized, purpose)] = _OtpRow(
            user_id=user_id,
            code_hash=code_hash,
            expires_in_seconds=expires_in_seconds,
        )

    def verify_otp_active(
        self,
        *,
        email_normalized: str,
        purpose: OtpPurpose,
        code_plain: str,
    ) -> bool:
        row = self._rows.get((email_normalized, purpose))
        if not row or row.consumed:
            return False
        return hash_otp(code_plain, self._pepper) == row.code_hash

    def consume_otp(self, *, email_normalized: str, purpose: OtpPurpose) -> None:
        row = self._rows.get((email_normalized, purpose))
        if row:
            row.consumed = True


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, OtpPurpose, str]] = []

    def send_otp_email(
        self,
        *,
        to_email: str,
        purpose: OtpPurpose,
        code_plain: str,
    ) -> None:
        self.sent.append((to_email, purpose, code_plain))


class FakeUserRepository:
    def __init__(self, users: dict[str, UserRecord]) -> None:
        self._by_email = {normalize_email(u.email): u for u in users.values()}
        self._by_id = dict(users)
        self.password_hashes: dict[str, str] = {}

    def get_by_email_normalized(self, email_normalized: str) -> UserRecord | None:
        return self._by_email.get(email_normalized)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        return self._by_id.get(user_id)

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        self.password_hashes[user_id] = password_hash
        u = self._by_id[user_id]
        u.has_password = True
        self._by_email[normalize_email(u.email)] = u


def _hash(p: str) -> str:
    return f"hashed:{p}"


class ForgotPasswordAuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pepper = "test-pepper"
        self.mailer = FakeMailer()
        self.otps = FakeOtpRepository(self.pepper)
        self.users = FakeUserRepository(
            {
                "1": UserRecord(
                    id="1",
                    email="a@example.com",
                    email_normalized="a@example.com",
                    has_password=True,
                    is_google_linked=False,
                    may_request_password_reset=True,
                    metadata={},
                ),
                "2": UserRecord(
                    id="2",
                    email="g@example.com",
                    email_normalized="g@example.com",
                    has_password=False,
                    is_google_linked=True,
                    may_request_password_reset=True,
                    metadata={},
                ),
            },
        )
        self.svc = ForgotPasswordAuthService(
            users=self.users,
            otps=self.otps,
            mailer=self.mailer,
            otp_pepper=self.pepper,
            hash_password=_hash,
        )

    def test_request_password_reset_sends_forgot_otp(self) -> None:
        r = self.svc.request_password_reset("a@example.com")
        self.assertTrue(r.success)
        self.assertEqual(len(self.mailer.sent), 1)
        self.assertEqual(self.mailer.sent[0][1], OtpPurpose.FORGOT_PASSWORD)

    def test_request_password_reset_unknown_email_no_mail(self) -> None:
        r = self.svc.request_password_reset("missing@example.com")
        self.assertTrue(r.success)
        self.assertEqual(len(self.mailer.sent), 0)

    def test_request_password_reset_google_only_no_mail(self) -> None:
        r = self.svc.request_password_reset("g@example.com")
        self.assertTrue(r.success)
        self.assertEqual(len(self.mailer.sent), 0)

    def test_reset_password_roundtrip(self) -> None:
        self.svc.request_password_reset("a@example.com")
        code = self.mailer.sent[-1][2]
        self.assertTrue(self.svc.verify_forgot_password_otp("a@example.com", code))
        r = self.svc.reset_password("a@example.com", code, "newpass12")
        self.assertTrue(r.success)
        self.assertEqual(self.users.password_hashes["1"], "hashed:newpass12")

    def test_initial_password_flow(self) -> None:
        r = self.svc.request_initial_password_otp(
            authenticated_user_id="2",
            email_must_match="g@example.com",
        )
        self.assertTrue(r.success)
        self.assertEqual(self.mailer.sent[-1][1], OtpPurpose.INITIAL_PASSWORD)
        code = self.mailer.sent[-1][2]
        self.assertTrue(self.svc.verify_initial_password_otp("g@example.com", code))
        r2 = self.svc.set_initial_password_with_otp(
            authenticated_user_id="2",
            email="g@example.com",
            otp_code=code,
            new_password="firstpass12",
        )
        self.assertTrue(r2.success)
        self.assertTrue(self.users.get_by_id("2") and self.users.get_by_id("2").has_password)
        self.assertEqual(self.users.password_hashes["2"], "hashed:firstpass12")


if __name__ == "__main__":
    unittest.main()
