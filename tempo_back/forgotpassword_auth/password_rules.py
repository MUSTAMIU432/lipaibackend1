from __future__ import annotations

import re

from .exceptions import WeakPasswordError

MIN_LEN = 8


def validate_new_password(plain: str) -> None:
    if not plain or len(plain) < MIN_LEN:
        raise WeakPasswordError(
            f"Password must be at least {MIN_LEN} characters.",
        )
    if not re.search(r"[A-Za-z]", plain) or not re.search(r"\d", plain):
        raise WeakPasswordError(
            "Password must include at least one letter and one number.",
        )
