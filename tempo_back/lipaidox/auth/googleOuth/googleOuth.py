"""
BACKEND ONLY (Django / Strawberry GraphQL in ``tempo_back``).

GraphQL ``googleAuth`` accepts **either**:

1) **Firebase ID tokens** — what both the web app and the mobile app send. Issued by
   Firebase (issuer ``securetoken.google.com/<FIREBASE_PROJECT_ID>``) and verified with
   **Firebase Admin** (``FirebaseAuthService.verify``), including revocation and
   disabled-account checks. Credentials: ``FIREBASE_CLIENT_EMAIL`` + ``FIREBASE_PRIVATE_KEY``
   (Render) or a gitignored service-account JSON (local). Does **not** use
   ``GOOGLE_OAUTH_CLIENT_ID``.

2) **Google ID tokens** (legacy) — mobile builds before 1.2.0 sent the raw Google token.
   Verified with ``verify_google_credential_jwt()`` against ``GOOGLE_OAUTH_CLIENT_ID``
   (and additional client IDs). Kept so already-installed APKs keep signing in.

The mutation routes by JWT ``iss``: Firebase tokens never go through GIS verification.

Credentials: only via ``django.conf.settings`` (``.env``) and optional local ``authjson`` files.
Never commit private keys. See ``lipaidox_backend/settings.py`` and ``.env.example``.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading

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
    android = (getattr(settings, "GOOGLE_OAUTH_ANDROID_CLIENT_ID", None) or "").strip()
    extra = (getattr(settings, "GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS", None) or "").strip()
    for part in [android, *extra.split(",")]:
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
# Firebase Admin
# ---------------------------------------------------------------------------


class FirebaseTokenError(ValueError):
    """A Firebase ID token was refused. ``str(e)`` is safe to show the user."""


def normalize_private_key(raw: str) -> str:
    """
    Turn a private key pasted into an env var back into real PEM.

    Render / `.env` values usually carry the key on one line with literal ``\n``
    sequences, sometimes still wrapped in the quotes copied from the JSON file.
    """
    key = (raw or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in ("'", '"'):
        key = key[1:-1]
    return key.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n").strip() + "\n"


def service_account_from_env() -> dict | None:
    """
    Service account from ``FIREBASE_PROJECT_ID`` + ``FIREBASE_CLIENT_EMAIL`` +
    ``FIREBASE_PRIVATE_KEY`` — the three values Render holds instead of a JSON file.
    """
    project_id = (getattr(settings, "FIREBASE_PROJECT_ID", None) or "").strip()
    client_email = (getattr(settings, "FIREBASE_CLIENT_EMAIL", None) or "").strip()
    private_key = getattr(settings, "FIREBASE_PRIVATE_KEY", None) or ""
    if not (client_email and private_key.strip()):
        return None
    if not project_id:
        logger.error("FIREBASE_CLIENT_EMAIL/FIREBASE_PRIVATE_KEY are set but FIREBASE_PROJECT_ID is not.")
        return None
    key = normalize_private_key(private_key)
    if "-----BEGIN PRIVATE KEY-----" not in key:
        logger.error("FIREBASE_PRIVATE_KEY does not look like a PEM private key.")
        return None
    return {
        "type": "service_account",
        "project_id": project_id,
        "client_email": client_email,
        "private_key": key,
        # Certificate() builds the token URI itself when this is present.
        "token_uri": "https://oauth2.googleapis.com/token",
    }


class FirebaseAuthService:
    """
    Process-wide Firebase Admin app, initialised once (thread-safe) on first use.

    Credential sources, first match wins:
      1. ``FIREBASE_CLIENT_EMAIL`` + ``FIREBASE_PRIVATE_KEY`` (+ ``FIREBASE_PROJECT_ID``) — Render.
      2. ``authjson`` helpers: gitignored JSON file / B64 / JSON env — local development.
      3. ``FIREBASE_SERVICE_ACCOUNT_PATH``.
    A key whose ``project_id`` differs from ``FIREBASE_PROJECT_ID`` is skipped: it can
    neither check revocation nor look users up in this project, and silently using it
    turns every sign-in into a confusing permission error.
    """

    _instance: FirebaseAuthService | None = None
    _lock = threading.Lock()

    def __new__(cls) -> FirebaseAuthService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.last_verify_error = None
            cls._instance.credential_source = None
        return cls._instance

    def ensure_initialized(self) -> None:
        """Initialize the default Firebase Admin app if credentials are configured (for any Admin SDK use)."""
        self._initialize()

    @property
    def initialized(self) -> bool:
        return bool(firebase_admin is not None and firebase_admin._apps)

    def _accept(self, account: dict | None, source: str, project_id: str) -> dict | None:
        if not account:
            return None
        sa_project = (account.get("project_id") or "").strip()
        if project_id and sa_project and sa_project != project_id:
            logger.error(
                "Ignoring Firebase service account from %s: it belongs to project %r, "
                "but FIREBASE_PROJECT_ID is %r. Download a key for %r.",
                source,
                sa_project,
                project_id,
                project_id,
            )
            return None
        return account

    def _initialize(self) -> None:
        if firebase_admin is None or firebase_credentials is None:
            logger.warning(
                "firebase-admin is not installed — Firebase ID token verification is disabled. "
                "Install with: pip install firebase-admin"
            )
            return
        if firebase_admin._apps:
            return

        with self._lock:
            if firebase_admin._apps:
                return
            project_id = (getattr(settings, "FIREBASE_PROJECT_ID", None) or "").strip()
            account: dict | None = None
            source = None

            account = self._accept(service_account_from_env(), "FIREBASE_CLIENT_EMAIL/FIREBASE_PRIVATE_KEY", project_id)
            if account:
                source = "env"

            if account is None:
                try:
                    from .authjson import load_firebase_service_account_dict

                    account = self._accept(load_firebase_service_account_dict(), "authjson", project_id)
                    if account:
                        source = "file"
                except Exception:
                    logger.exception("Could not load Firebase credentials from authjson.")

            cred_path = (getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", None) or "").strip()
            if account is None and cred_path and os.path.isfile(cred_path):
                try:
                    with open(cred_path, encoding="utf-8") as f:
                        account = self._accept(json.load(f), cred_path, project_id)
                    if account:
                        source = "path"
                except Exception:
                    logger.exception("Invalid FIREBASE_SERVICE_ACCOUNT_PATH credential file.")

            if account and not project_id:
                project_id = (account.get("project_id") or "").strip()

            if not project_id:
                logger.warning("FIREBASE_PROJECT_ID unset — Firebase Admin not started.")
                return

            try:
                if account:
                    firebase_admin.initialize_app(
                        firebase_credentials.Certificate(account), {"projectId": project_id}
                    )
                    self.credential_source = source
                    logger.info("Firebase Admin initialized for %s (credentials: %s).", project_id, source)
                elif getattr(settings, "FIREBASE_ALLOW_APPLICATION_DEFAULT_CREDENTIALS", False):
                    firebase_admin.initialize_app(options={"projectId": project_id})
                    self.credential_source = "adc"
                    logger.info("Firebase Admin initialized with Application Default Credentials (%s).", project_id)
                else:
                    logger.error(
                        "Firebase Admin needs a service account for %s. Set FIREBASE_CLIENT_EMAIL and "
                        "FIREBASE_PRIVATE_KEY (see .env.example).",
                        project_id,
                    )
            except Exception:
                logger.exception("Firebase Admin initialization failed.")

    def verify(self, id_token: str) -> dict:
        """
        Verify a Firebase ID token and return its claims.

        Checks signature, expiry, audience (= ``FIREBASE_PROJECT_ID``) and — unless
        ``FIREBASE_CHECK_REVOKED`` is off — that the token was not revoked and the
        Firebase user is neither disabled nor deleted.

        Raises:
            FirebaseTokenError: with a message safe to return to the client.
        """
        id_token = normalize_google_id_token(id_token)
        if not id_token:
            raise FirebaseTokenError("Missing sign-in token.")

        if settings.DEBUG and getattr(settings, "FIREBASE_ALLOW_TEST_TOKENS", False):
            fake = _DEBUG_TEST_TOKENS.get(id_token)
            if fake:
                return dict(fake)

        self._initialize()
        if not self.initialized:
            raise FirebaseTokenError("Sign-in with Google is not available right now. Please try again later.")

        check_revoked = bool(getattr(settings, "FIREBASE_CHECK_REVOKED", True))
        try:
            return firebase_auth.verify_id_token(
                id_token,
                check_revoked=check_revoked,
                clock_skew_seconds=min(int(getattr(settings, "FIREBASE_CLOCK_SKEW_SECONDS", 10) or 0), 60),
            )
        # Order matters: Expired/Revoked are subclasses of InvalidIdTokenError.
        except firebase_auth.ExpiredIdTokenError as e:
            raise FirebaseTokenError("Your sign-in expired. Please sign in again.") from e
        except firebase_auth.RevokedIdTokenError as e:
            raise FirebaseTokenError("This sign-in was revoked. Please sign in again.") from e
        except firebase_auth.UserDisabledError as e:
            raise FirebaseTokenError("This Google account has been disabled for this app.") from e
        except firebase_auth.UserNotFoundError as e:
            raise FirebaseTokenError("This sign-in belongs to an account that no longer exists.") from e
        except firebase_auth.InvalidIdTokenError as e:
            logger.info("Rejected Firebase ID token: %s", e)
            raise FirebaseTokenError("Invalid sign-in token. Please sign in again.") from e
        except firebase_auth.CertificateFetchError as e:
            logger.warning("Could not fetch Firebase public keys: %s", e)
            raise FirebaseTokenError("Couldn't verify your sign-in right now. Please try again.") from e
        except ValueError as e:  # malformed token / wrong type
            raise FirebaseTokenError("Invalid sign-in token. Please sign in again.") from e
        except Exception as e:  # e.g. revocation lookup denied — a server configuration problem
            logger.exception("Firebase ID token verification failed unexpectedly.")
            raise FirebaseTokenError(
                "Sign-in with Google is not available right now. Please try again later."
            ) from e

    def verify_token(self, id_token: str) -> dict | None:
        """Compatibility wrapper around :meth:`verify`: claims or ``None`` (reason in ``last_verify_error``)."""
        self.last_verify_error = None
        try:
            return self.verify(id_token)
        except FirebaseTokenError as e:
            self.last_verify_error = str(e)
            return None


# Local-development stand-ins, accepted only when DEBUG *and* FIREBASE_ALLOW_TEST_TOKENS are on.
_DEBUG_TEST_TOKENS = {
    "test-google-token": {
        "uid": "test_google_123",
        "email": "tester_google@example.com",
        "name": "Test Google User",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com", "identities": {"google.com": ["test_google_sub_123"]}},
    },
}


def firebase_google_identity(claims: dict) -> str | None:
    """The Google account id (``sub``) behind a Firebase token signed in with Google."""
    identities = (claims.get("firebase") or {}).get("identities") or {}
    ids = identities.get("google.com") or []
    return str(ids[0]) if ids else None


def firebase_sign_in_provider(claims: dict) -> str:
    return str((claims.get("firebase") or {}).get("sign_in_provider") or "")
