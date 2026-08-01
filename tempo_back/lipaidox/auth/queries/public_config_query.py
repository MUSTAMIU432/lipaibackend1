"""Public auth-related values safe to expose without login (Web OAuth client IDs are public)."""

from __future__ import annotations

import base64
import json
from typing import Optional
from urllib.parse import urlencode

import strawberry
from django.conf import settings

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _build_google_oauth_authorization_url(signup_role: Optional[str]) -> str:
    client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or "").strip()
    redirect_uri = (getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", None) or "").strip()
    if not client_id or not redirect_uri:
        return ""

    scopes = (getattr(settings, "GOOGLE_OAUTH_SCOPES", None) or "openid email profile").strip()
    if not scopes:
        scopes = "openid email profile"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scopes,
    }

    if signup_role and str(signup_role).strip():
        payload = json.dumps(
            {"signupRole": str(signup_role).strip()},
            separators=(",", ":"),
        ).encode("utf-8")
        params["state"] = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


@strawberry.type
class PublicAuthConfigQuery:
    @strawberry.field
    def google_oauth_client_id(self) -> str:
        """Google Sign-In Web client ID — same as GIS `client_id`; configured server-side only."""
        return (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or "").strip()

    @strawberry.field
    def google_oauth_authorization_url(
        self,
        signup_role: Optional[str] = None,
    ) -> str:
        """
        Full Google OAuth 2.0 authorization URL for redirect-based sign-in.
        Returns "" if `GOOGLE_OAUTH_CLIENT_ID` or `GOOGLE_OAUTH_REDIRECT_URI` is unset.
        Optional `signupRole` is embedded in the `state` param (base64url JSON) for the callback.
        """
        return _build_google_oauth_authorization_url(signup_role)
