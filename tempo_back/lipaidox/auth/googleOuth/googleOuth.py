"""
BACKEND ONLY (Django / Strawberry GraphQL in ``tempo_back``).

GraphQL ``googleAuth`` accepts **either**:

1) **Firebase ID tokens** (recommended when the app uses Firebase Auth) — issued by Firebase
   with issuer ``securetoken.google.com``. Verified with **Firebase Admin** using your
   **Firebase service account** JSON (``FIREBASE_*`` settings and/or ``authjson`` helpers).
   This path does **not** use ``GOOGLE_OAUTH_CLIENT_ID``.

2) **Google Identity Services (GIS) JWT** (optional legacy / alternate client) — Web client
   ``credential`` JWT. Verified with ``verify_google_credential_jwt()`` using
   ``GOOGLE_OAUTH_CLIENT_ID`` (and optional additional client IDs).

The mutation routes by JWT ``iss``: Firebase tokens never go through GIS verification.

Credentials: only via ``django.conf.settings`` (``.env``) and optional local ``authjson`` files.
Never commit private keys. See ``lipaidox_backend/settings.py`` and ``.env.example``.
"""

from __future__ import annotations

import base64
import json
import logging
import os

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials as firebase_credentials
except ImportError:  # optional — GIS `googleAuth` uses google-auth only
    firebase_admin = None  # type: ignore[misc, assignment]
    firebase_auth = None  # type: ignore[misc, assignment]
    firebase_credentials = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

_GOOGLE_ISSUERS = frozenset(("accounts.google.com", "https://accounts.google.com"))


def _project_id_from_service_account_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return (json.load(f).get("project_id") or "").strip()
    except Exception:
        return ""


def normalize_google_id_token(raw: str) -> str:
    """Strip whitespace, optional ``Bearer `` prefix, and stray JSON quotes from the client."""
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip()
    if s.lower().startswith("bearer "):
        s = s[7:].strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    return s


def _unverified_jwt_payload(token: str) -> dict | None:
    """Decode JWT payload without verification (issuer / audience hints only)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        body = parts[1]
        pad = "=" * ((4 - len(body) % 4) % 4)
        raw = base64.urlsafe_b64decode(body + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def peek_google_jwt_issuer(token: str) -> str | None:
    """Return JWT ``iss`` claim without verifying the signature (routing GIS vs Firebase)."""
    payload = _unverified_jwt_payload(normalize_google_id_token(token))
    if not payload:
        return None
    iss = payload.get("iss")
    return str(iss).strip() if iss else None


# ---------------------------------------------------------------------------
# GIS / OAuth 2.0 Web client JWT (GraphQL `googleAuth`)
# ---------------------------------------------------------------------------


def _google_oauth_audiences() -> list[str]:
    """OAuth Web client IDs allowed as JWT `aud` — from settings / env."""
    ids: list[str] = []
    main = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None) or "").strip()
    if main:
        ids.append(main)
    extra = (getattr(settings, "GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS", None) or "").strip()
    for part in extra.split(","):
        p = part.strip()
        if p and p not in ids:
            ids.append(p)
    return ids


def verify_google_credential_jwt(raw_token: str) -> dict:
    """
    Validate a Google Sign-In JWT (`credential` from GIS) and return decoded claims.

    Raises:
        ValueError: Safe client-facing message (never echo raw token or stack traces).
    """
    audiences = _google_oauth_audiences()
    if not audiences:
        raise ValueError("Google sign-in is not configured on the server.")

    token = normalize_google_id_token(raw_token)
    if not token:
        raise ValueError("Missing Google credential.")

    skew = int(getattr(settings, "GOOGLE_OAUTH_CLOCK_SKEW_SECONDS", 120) or 120)

    last_error: ValueError | None = None
    idinfo: dict | None = None
    for client_id in audiences:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                client_id,
                clock_skew_in_seconds=skew,
            )
            break
        except ValueError as e:
            last_error = e
            continue

    if idinfo is None:
        payload = _unverified_jwt_payload(token)
        if settings.DEBUG and payload:
            logger.warning(
                "GIS JWT verify failed (check GOOGLE_OAUTH_CLIENT_ID matches browser client): "
                "iss=%s aud=%s",
                payload.get("iss"),
                payload.get("aud"),
            )
        raise ValueError(
            "Invalid or expired Google sign-in. Please try again."
        ) from last_error

    if idinfo.get("iss") not in _GOOGLE_ISSUERS:
        raise ValueError("Invalid Google token issuer.")

    return idinfo


# ---------------------------------------------------------------------------
# Firebase Admin (optional)
# ---------------------------------------------------------------------------


class FirebaseAuthService:
    """Lazy Firebase Admin app for `auth.verify_id_token` on Firebase client tokens."""

    _instance: FirebaseAuthService | None = None

    def __new__(cls) -> FirebaseAuthService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.last_verify_error = None
        return cls._instance

    def ensure_initialized(self) -> None:
        """Initialize the default Firebase Admin app if credentials are configured (for any Admin SDK use)."""
        self._initialize()

    def _initialize(self) -> None:
        if firebase_admin is None or firebase_credentials is None:
            logger.warning(
                "firebase-admin is not installed — Firebase ID token verification is disabled. "
                "GIS Google sign-in still works. Install with: pip install firebase-admin"
            )
            return

        project_id = (getattr(settings, "FIREBASE_PROJECT_ID", None) or "").strip()
        cred_path = (getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", None) or "").strip()

        if firebase_admin._apps:
            return

        cred = None

        # 1) authjson.py hub first: INLINE_FIREBASE_SERVICE_ACCOUNT, authjson_secrets, env B64/JSON,
        #    and JSON files next to authjson.py (see lipaidox.auth.googleOuth.authjson).
        try:
            from .authjson import load_firebase_service_account_dict

            account = load_firebase_service_account_dict()
            if account:
                cred = firebase_credentials.Certificate(account)
                if not project_id:
                    project_id = (account.get("project_id") or "").strip()
                logger.info("Firebase Admin credentials loaded via authjson.")
        except Exception:
            logger.exception("Could not load Firebase credentials from authjson.")

        # 2) FIREBASE_SERVICE_ACCOUNT_PATH (.env or auto-discovered path in settings)
        if cred is None and cred_path:
            if os.path.isfile(cred_path):
                try:
                    cred = firebase_credentials.Certificate(cred_path)
                    logger.info("Firebase Admin will use FIREBASE_SERVICE_ACCOUNT_PATH.")
                    if not project_id:
                        project_id = _project_id_from_service_account_file(cred_path)
                        if project_id:
                            logger.info(
                                "FIREBASE_PROJECT_ID was empty; using project_id from service account file."
                            )
                except Exception:
                    logger.exception("Invalid FIREBASE_SERVICE_ACCOUNT_PATH credential file.")
            else:
                logger.error(
                    "FIREBASE_SERVICE_ACCOUNT_PATH is set but file not found: %s.",
                    cred_path,
                )

        if not project_id:
            logger.warning(
                "FIREBASE_PROJECT_ID unset — Firebase Admin not started (optional)."
            )
            return

        allow_adc = bool(
            getattr(
                settings,
                "FIREBASE_ALLOW_APPLICATION_DEFAULT_CREDENTIALS",
                False,
            )
        )

        try:
            if cred is not None:
                firebase_admin.initialize_app(cred, {"projectId": project_id})
                logger.info("Firebase Admin initialized with service account credentials.")
            elif allow_adc:
                firebase_admin.initialize_app(options={"projectId": project_id})
                logger.info(
                    "Firebase Admin initialized with Application Default Credentials (project=%s).",
                    project_id,
                )
            else:
                logger.error(
                    "Firebase ID token verification needs a service account, but none was loaded. "
                    "Configure lipaidox.auth.googleOuth.authjson (INLINE dict or JSON beside authjson.py), "
                    "or FIREBASE_SERVICE_ACCOUNT_PATH / FIREBASE_SERVICE_ACCOUNT_B64. "
                    "See authjson.py module docstring."
                )
        except Exception:
            logger.exception("Firebase Admin initialization failed.")

    def verify_token(self, id_token: str) -> dict | None:
        """
        Verify a Firebase ID token. Returns claims or None.

        DEBUG: ``test-google-token`` / ``test-apple-token`` for local dev only.
        """
        id_token = normalize_google_id_token(id_token)
        if not id_token:
            return None

        self.last_verify_error = None

        if settings.DEBUG:
            if id_token == "test-google-token":
                return {
                    "uid": "test_google_123",
                    "email": "tester_google@example.com",
                    "name": "Test Google User",
                    "email_verified": True,
                }
            if id_token == "test-apple-token":
                return {
                    "uid": "test_apple_456",
                    "email": "tester_apple@example.com",
                    "name": "Test Apple User",
                    "email_verified": True,
                }

        self._initialize()
        if firebase_admin is None or firebase_auth is None or not firebase_admin._apps:
            hint = (
                "Firebase Admin SDK is not initialized. Place a valid "
                "`firebase-service-account.json` in `lipaidox/auth/googleOuth/` (next to "
                "`authjson.py`), or set `FIREBASE_SERVICE_ACCOUNT_PATH` in `.env` to the full path."
            )
            if settings.DEBUG:
                try:
                    from .authjson import credential_lookup_hint

                    hint = f"{hint} {credential_lookup_hint()}"
                except Exception:
                    pass
            self.last_verify_error = hint
            logger.error(
                "googleAuth: Firebase ID token received but Admin SDK is not running — %s",
                self.last_verify_error,
            )
            return None
        try:
            return firebase_auth.verify_id_token(id_token)
        except Exception as e:
            self.last_verify_error = str(e)
            logger.error("Firebase token verification failed: %s", e, exc_info=settings.DEBUG)
            return None
