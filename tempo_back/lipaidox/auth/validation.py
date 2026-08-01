"""
Signup email & password rules — keep in sync with FRT-Lipaidox `lib/auth-validation.ts`.

Account active / duplicate-email policy: `lipaidox.auth.user_eligibility`.
"""

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

EMAIL_MAX_LEN = 254
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128
# Aligned with frontend `SPECIAL_CHAR_SET`
_SPECIAL_CHAR_SET = frozenset(
    '!@#$%^&*()_+-=[]{};\':"\\|,.<>/?`~'
)


def normalize_signup_email(email: str) -> str:
    if not email or not isinstance(email, str):
        raise Exception("Email is required.")
    normalized = email.strip()
    # Common client bugs: JSON/JS sends the word "null" / "undefined" as a string.
    if normalized.lower() in frozenset(("null", "undefined", "none")):
        raise Exception("Email is required.")
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in "\"'":
        normalized = normalized[1:-1].strip()
    if not normalized:
        raise Exception("Email is required.")
    if len(normalized) > EMAIL_MAX_LEN:
        raise Exception("Email address is too long.")
    try:
        validate_email(normalized)
    except ValidationError:
        raise Exception("Enter a valid email address.")
    return normalized.lower()


def validate_signup_password(password: str) -> None:
    if not password or not isinstance(password, str):
        raise Exception("Password is required.")
    if len(password) < PASSWORD_MIN_LEN:
        raise Exception(
            f"Password must be at least {PASSWORD_MIN_LEN} characters."
        )
    if len(password) > PASSWORD_MAX_LEN:
        raise Exception("Password is too long.")
    if not re.search(r"[A-Z]", password):
        raise Exception("Password must include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise Exception("Password must include at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise Exception("Password must include at least one number.")
    if not any(c in _SPECIAL_CHAR_SET for c in password):
        raise Exception(
            "Password must include at least one special character "
            "(! @ # $ % ^ & * and similar)."
        )
