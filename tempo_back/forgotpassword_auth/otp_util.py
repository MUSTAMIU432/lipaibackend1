from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_six_digit_code() -> str:
    """Cryptographically secure 6-digit string (allows leading 0)."""
    n = secrets.randbelow(1_000_000)
    return f"{n:06d}"


def hash_otp(code: str, secret_pepper: str) -> str:
    digest = hmac.new(
        secret_pepper.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def normalize_email(email: str) -> str:
    return email.strip().lower()
