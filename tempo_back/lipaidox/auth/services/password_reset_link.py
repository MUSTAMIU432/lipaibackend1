"""Build SPA URLs for opaque password-reset tokens (query string)."""

from __future__ import annotations

from urllib.parse import urlencode


def build_password_reset_url(
    *, frontend_origin: str, frontend_path: str, token: str
) -> str:
    origin = (frontend_origin or "").rstrip("/")
    path = (frontend_path or "/reset-password").strip() or "/reset-password"
    if not path.startswith("/"):
        path = "/" + path
    return f"{origin}{path}?{urlencode({'token': token})}"
