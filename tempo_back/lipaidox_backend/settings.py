"""
Django settings for lipaidox_backend project.
"""

import json
import logging
from pathlib import Path

from decouple import AutoConfig
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
_settings_log = logging.getLogger(__name__)


def _is_usable_firebase_service_account_file(path: str | Path) -> bool:
    """True if path is a non-empty file with valid Firebase/GCP service account JSON."""
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size < 80:
            return False
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        if data.get("type") != "service_account":
            return False
        return bool(
            data.get("private_key")
            and data.get("client_email")
            and data.get("project_id")
        )
    except Exception:
        return False


def _parse_firebase_service_account_supplement(path: str | Path) -> dict:
    """
    Read ``project_id`` from the service account JSON when ``FIREBASE_PROJECT_ID`` is not in ``.env``.

    Password reset for Firebase users is handled in the **browser** (``sendPasswordResetEmail``);
    do not store Web API keys in this file for Django.
    """
    out: dict = {}
    try:
        p = Path(path)
        if not p.is_file():
            return out
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return out
    if not isinstance(data, dict) or data.get("type") != "service_account":
        return out

    pid = (data.get("project_id") or "").strip()
    if pid:
        out["project_id"] = pid

    return out


# Always read `.env` from the project root (same folder as `manage.py`), not from CWD.
config = AutoConfig(search_path=str(BASE_DIR))


def _config_bool(name: str, default: bool = False) -> bool:
    raw = str(config(name, default=str(default))).strip().lower()
    if raw in {"1", "true", "t", "yes", "y", "on", "debug", "development", "dev"}:
        return True
    if raw in {"0", "false", "f", "no", "n", "off", "release", "production", "prod"}:
        return False
    _settings_log.warning("Invalid %s=%r; falling back to %s", name, raw, default)
    return default

# SECURITY
SECRET_KEY = config("SECRET_KEY", default="django-insecure-2cbgt-@42*6h@y)_#s^z6j&%9-t2x+6#l!(d!w%o39b3e6_+=^")
DEBUG = _config_bool("DEBUG", default=False)
# Strip whitespace; ignore empty segments (trailing commas / blank lines in `.env`).
# Defaults cover local dev + the Tauri Android emulator host alias (10.0.2.2).
# For a PHYSICAL device add your host's LAN IP to the ALLOWED_HOSTS env var, e.g.
# ALLOWED_HOSTS=127.0.0.1,localhost,10.0.2.2,192.168.1.100
_allowed = [
    h.strip()
    for h in config("ALLOWED_HOSTS", default="127.0.0.1,localhost,10.0.2.2,0.0.0.0").split(",")
    if h.strip()
]
ALLOWED_HOSTS = _allowed or ["127.0.0.1", "localhost", "10.0.2.2"]
# In DEBUG, accept any Host header so LAN-IP access from a physical device works
# without listing every IP. Production must set ALLOWED_HOSTS explicitly.
if DEBUG:
    ALLOWED_HOSTS = ["*"]

# -----------------------------
# Installed Applications
# -----------------------------
INSTALLED_APPS = [
    # Django default apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    "strawberry_django",
    "rest_framework",
    "corsheaders",

    # Multi-tenancy middleware app
    "multitenant",

    # Platform Modules
    "lipaidox",                 
    "lipaidox.auth",
    "lipaidox.onboarding",
    "lipaidox.creator_profile",
    "lipaidox.content_classification",
    "lipaidox.kyc",
    "lipaidox.payment",
    "lipaidox.monetization",
    "lipaidox.content",
    "lipaidox.subscriptions",
    "lipaidox.ppv",
    "lipaidox.tips",
    "lipaidox.live_streaming",
    "lipaidox.wallet",
    "lipaidox.ai_intelligence",
    "lipaidox.security",
    "lipaidox.notifications",
    "lipaidox.admin_panel",
    "lipaidox.analytics",
    "lipaidox.messaging",
    "lipaidox.creator_plans",
    "lipaidox.credits",
    "lipaidox.recommendation",
    "lipaidox.lms_identity",
    "lipaidox.lms_content",
    "lipaidox.lms_learning",
    "lipaidox.lms_community",
    "lipaidox.lms_certification",
    "lipaidox.lms_skills",
    "lipaidox.lms_performance",
    "lipaidox.lms_financial",
    "lipaidox.lms_careers",
    "lipaidox.lms_messages",
    "lipaidox.lms_notifications",
    "lipaidox.lms_cohorts",
    "lipaidox.lms_employer",
    "lipaidox.lms_onboarding",
    "lipaidox.lost_found",
]

AUTH_USER_MODEL = "lipaidox_auth.User"

# -----------------------------
# Middleware
# -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "multitenant.middleware.TenantMiddleware",
]

ROOT_URLCONF = "lipaidox_backend.urls"

# -----------------------------
# Templates
# -----------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "lipaidox_backend.wsgi.application"

# -----------------------------
# Database
# -----------------------------
if config("USE_SQLITE", default=False, cast=bool):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="lipaidox2"),
            "USER": config("DB_USER", default="lipaiduser"),
            "PASSWORD": config("DB_PASSWORD", default="lipai123"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

# -----------------------------
# Password Validators
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------
# Internationalization
# -----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -----------------------------
# Static Files
# -----------------------------
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------
# Media Files (user uploads)
# -----------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Accept larger GraphQL JSON bodies (e.g. upload metadata/data URLs sent by the frontend).
# Keep this configurable via .env for local/prod tuning.
DATA_UPLOAD_MAX_MEMORY_SIZE = config(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=25 * 1024 * 1024,  # 25 MB
    cast=int,
)
FILE_UPLOAD_MAX_MEMORY_SIZE = config(
    "FILE_UPLOAD_MAX_MEMORY_SIZE",
    default=25 * 1024 * 1024,  # 25 MB
    cast=int,
)

# -----------------------------
# CORS
# -----------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-tenant-id",
    "x-requested-with",
]

# -----------------------------
# REST Framework
# -----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# -----------------------------
# JWT Configuration (PyJWT — used by GraphQL auth layer)
# -----------------------------
JWT_SECRET_KEY = config("JWT_SECRET_KEY", default=SECRET_KEY)

# -----------------------------
# WhatsApp Business API Configuration
# -----------------------------
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_ACCESS_TOKEN = config("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_WEBHOOK_TOKEN = config("WHATSAPP_WEBHOOK_TOKEN", default="")

# -----------------------------
# Email (SMTP) — read from `.env` next to `manage.py` (python-decouple `config()`).
# -----------------------------
# Password-reset **OTP** (`requestPasswordReset` → `send_password_reset_otp_email`) uses
# Django `send_mail`. Fill the gaps below in `.env` for real delivery.
#
# | Variable                 | You fill in…                                      |
# |--------------------------|---------------------------------------------------|
# | EMAIL_HOST               | SMTP host (e.g. smtp.sendgrid.net)                |
# | EMAIL_PORT               | Usually 587 (TLS) or 465 (SSL)                    |
# | EMAIL_USE_TLS / _SSL     | Match your provider                               |
# | EMAIL_HOST_USER          | SMTP username (often same as “from” mailbox)      |
# | EMAIL_HOST_PASSWORD      | SMTP password or app-specific secret              |
# | DEFAULT_FROM_EMAIL       | Visible “From:” (must be allowed by provider)     |
# | SERVER_EMAIL             | Optional; defaults from DEFAULT_FROM_EMAIL        |
# | EMAIL_TIMEOUT            | Seconds (default 30)                              |
# | EMAIL_BACKEND            | Optional override (rare; leave empty for auto)   |
#
# If **EMAIL_HOST** is left empty → `console` email backend: OTP still runs, body prints
# in the **runserver terminal** (good for local GraphQL + Next `/forgot-password` tests).
#
# Also set **FRONTEND_ORIGIN** and **PASSWORD_RESET_FRONTEND_PATH** above for *link* reset;
# OTP emails only need a valid From + SMTP (or console).
EMAIL_HOST = (config("EMAIL_HOST", default="") or "").strip()
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = (config("EMAIL_HOST_USER", default="") or "").strip()
EMAIL_HOST_PASSWORD = (config("EMAIL_HOST_PASSWORD", default="") or "").strip()
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=int)
DEFAULT_FROM_EMAIL = (config("DEFAULT_FROM_EMAIL", default="") or "").strip()
SERVER_EMAIL = (config("SERVER_EMAIL", default="") or "").strip()

_email_backend_explicit = (config("EMAIL_BACKEND", default="") or "").strip()
if _email_backend_explicit:
    EMAIL_BACKEND = _email_backend_explicit
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if not DEFAULT_FROM_EMAIL and EMAIL_HOST_USER:
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
if not SERVER_EMAIL:
    SERVER_EMAIL = DEFAULT_FROM_EMAIL or "root@localhost"

# Django's SMTP backend raises if both are True — fail fast with a clear message.
if EMAIL_HOST and EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        "EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True. "
        "Use port 587 + EMAIL_USE_TLS=True + EMAIL_USE_SSL=False, "
        "or port 465 + EMAIL_USE_SSL=True + EMAIL_USE_TLS=False."
    )
if EMAIL_HOST and "@" in EMAIL_HOST:
    _settings_log.warning(
        "EMAIL_HOST is %r — this is usually wrong. It must be the SMTP server hostname "
        "(e.g. smtp.gmail.com), not an email address.",
        EMAIL_HOST,
    )

# SPA origin for links in app emails (password reset link, etc.).
FRONTEND_ORIGIN = config("FRONTEND_ORIGIN", default="http://localhost:3000").rstrip("/")

# ── Payments / gateway ────────────────────────────────────────────────────────
# Which PaymentGateway implementation funds wallets. "simulated" (default) settles
# instantly with no real money; "nbc" charges NBC/Haminass Pay (card + M-Pesa,
# async — settled by the webhook at /payments/callback/nbc/).
PAYMENT_GATEWAY_DEFAULT = config("PAYMENT_GATEWAY_DEFAULT", default="simulated").strip()

# NBC / Haminass Pay. The secret key lives ONLY here on the server.
NBC_API_KEY = config("NBC_API_KEY", default="").strip()
NBC_API_BASE = config("NBC_API_BASE", default="https://accesspay.eopsprimax.com").rstrip("/")
# Fallback currency when a caller doesn't specify one. The platform wallet/prices
# are USD today, so default to USD (NBC accepts USD or TZS). M-Pesa settlement is
# TZS-native — align prices to TZS before relying on it in production.
NBC_CURRENCY = config("NBC_CURRENCY", default="USD").strip().upper()
# M-Pesa settles in TZS and mobile-money payouts are TZS-native, but the wallet
# and prices are USD. This reference rate converts a USD amount to the TZS figure
# NBC must charge/send. Override per market, or wire to a live rate feed later.
NBC_USD_TO_TZS = config("NBC_USD_TO_TZS", default=2600, cast=float)
# The currency NBC is actually settled in. Live keys are provisioned per-market and
# reject anything else (the current key 502s on USD), so every leg — card included,
# not just M-Pesa — is converted to this before it goes on the wire. The Charge row
# and the wallet stay in their own currency, so fulfillment is unaffected.
NBC_SETTLEMENT_CURRENCY = config("NBC_SETTLEMENT_CURRENCY", default="TZS").strip().upper()
# Where NBC returns the browser after a card payment. Its host must be pre-approved
# on the API key or NBC returns 403 — until it is, leave this empty and NBC's own
# default return page is used (the SPA status poll still settles the charge).
NBC_REDIRECT_URL = config("NBC_REDIRECT_URL", default="").strip()
# Path on the SPA for the “new password” form (link in password-reset emails).
PASSWORD_RESET_FRONTEND_PATH = (
    config("PASSWORD_RESET_FRONTEND_PATH", default="/reset-password").strip() or "/reset-password"
)
if not PASSWORD_RESET_FRONTEND_PATH.startswith("/"):
    PASSWORD_RESET_FRONTEND_PATH = "/" + PASSWORD_RESET_FRONTEND_PATH

# OTP email: optional SPA link (same FRONTEND_ORIGIN) so the app can pre-fill the six digits.
PASSWORD_RESET_OTP_LINK_ENABLED = config(
    "PASSWORD_RESET_OTP_LINK_ENABLED", default=True, cast=bool
)
PASSWORD_RESET_OTP_PREFILL_PATH = (
    config("PASSWORD_RESET_OTP_PREFILL_PATH", default="/forgot-password").strip()
    or "/forgot-password"
)
if not PASSWORD_RESET_OTP_PREFILL_PATH.startswith("/"):
    PASSWORD_RESET_OTP_PREFILL_PATH = "/" + PASSWORD_RESET_OTP_PREFILL_PATH

# When True: do not send OTP email; return the code in GraphQL as ``inlineOtp`` (SPA auto-fill).
# Leave False in production unless you fully accept the risk (anyone who can call the API sees codes).
PASSWORD_RESET_INLINE_OTP = config(
    "PASSWORD_RESET_INLINE_OTP",
    default=False,
    cast=bool,
)

# Same inline-OTP pattern for email address verification (step 2 of onboarding wizard).
EMAIL_VERIFICATION_INLINE_OTP = config(
    "EMAIL_VERIFICATION_INLINE_OTP",
    default=False,
    cast=bool,
)

# ---------------------------------------------------------------------------
# Google Sign-In (OAuth 2.0 Web client) — used by GraphQL `googleAuth` + public config queries
# ---------------------------------------------------------------------------
# SECURITY & OPS:
#   • Put real values only in `.env` (or the host secret manager). Never commit `.env`.
#   • GOOGLE_OAUTH_CLIENT_ID is a *public* identifier (browser-visible); still use env
#     per environment so dev/staging/prod don’t share the wrong client.
#   • The Web client ID here MUST match the one in your Next app (e.g. NEXT_PUBLIC_* or
#     the client id you pass to Google Identity Services). Same Google Cloud project as
#     Firebase if you use both.
#   • Service account keys / JSON files are SECRET: chmod 600, never git, rotate if leaked.
#
# Include in `.env` (see `.env.example` in this repo):
#   GOOGLE_OAUTH_CLIENT_ID
#   GOOGLE_OAUTH_REDIRECT_URI          # redirect-based OAuth only; must match Console
#   GOOGLE_OAUTH_SCOPES                # optional override
#   GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS # optional; comma-separated extra audiences
#
# Primary Web client ID (GIS `credential` JWT `aud` must match one of these).
GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="").strip()
# Optional: comma-separated OAuth client IDs to accept in addition to the primary (e.g.
# second Web client or env-specific client). Never put service account client emails here.
GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS = config(
    "GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS",
    default="",
).strip()
# Web redirect URL registered in Google Cloud Console (exact string match).
# Required for GraphQL `googleOauthAuthorizationUrl`; if empty, that query returns "".
GOOGLE_OAUTH_REDIRECT_URI = config("GOOGLE_OAUTH_REDIRECT_URI", default="").strip()
GOOGLE_OAUTH_SCOPES = config(
    "GOOGLE_OAUTH_SCOPES",
    default="openid email profile",
).strip()
# Max seconds of clock skew allowed when verifying GIS JWTs with google-auth (default 120).
GOOGLE_OAUTH_CLOCK_SKEW_SECONDS = config(
    "GOOGLE_OAUTH_CLOCK_SKEW_SECONDS",
    default=120,
    cast=int,
)

# ---------------------------------------------------------------------------
# Google Maps / Places API  (MAP_API key in .env)
# ---------------------------------------------------------------------------
GOOGLE_MAPS_API_KEY = config("MAP_API", default="").strip()

# ---------------------------------------------------------------------------
# Firebase Admin SDK — `lipaidox.auth.googleOuth.FirebaseAuthService`
# ---------------------------------------------------------------------------
# Verifies **Firebase Auth ID tokens** (issuer securetoken.google.com). Independent of
# GOOGLE_OAUTH_CLIENT_ID (that is only for optional GIS / non-Firebase JWT clients).
#
# Include in `.env`:
#   FIREBASE_PROJECT_ID              — Firebase / GCP project id (identifier, not secret)
#   FIREBASE_SERVICE_ACCOUNT_PATH  — path to downloaded JSON key file (SECRET; not in git)
#
# Optional dev fallback: gitignored JSON next to ``authjson.py``, or
# FIREBASE_SERVICE_ACCOUNT_B64 / FIREBASE_SERVICE_ACCOUNT_JSON in ``.env``.
# See ``lipaidox.auth.googleOuth.authjson``.
#
# Resolve the service account file first, then fill FIREBASE_PROJECT_ID from JSON if unset
# (see ``_parse_firebase_service_account_supplement``).
_FIREBASE_SA_PATH_ENV = config("FIREBASE_SERVICE_ACCOUNT_PATH", default="").strip()
if _FIREBASE_SA_PATH_ENV:
    _raw = _FIREBASE_SA_PATH_ENV
    _p = Path(_raw)
    if not _p.is_absolute():
        _p = (BASE_DIR / _p).resolve()
    else:
        _p = _p.resolve()
    _raw_path = str(_p)
    if _is_usable_firebase_service_account_file(_raw_path):
        FIREBASE_SERVICE_ACCOUNT_PATH = _raw_path
    else:
        _settings_log.warning(
            "FIREBASE_SERVICE_ACCOUNT_PATH is set but file is missing or not valid service "
            "account JSON (empty placeholder?): %s — ignoring; use googleOuth/firebase-service-account.json.",
            _raw_path,
        )
        FIREBASE_SERVICE_ACCOUNT_PATH = ""
else:
    # Auto-pick a downloaded key if present (skip empty/invalid placeholder files).
    _FIREBASE_SA_CANDIDATES = (
        BASE_DIR / "firebase-service-account.json",
        BASE_DIR / "secrets" / "firebase-service-account.json",
        BASE_DIR / "lipaidox" / "auth" / "googleOuth" / "firebase-service-account.json",
        BASE_DIR / "lipaidox" / "auth" / "googleOuth" / "firebase-service-account.local.json",
    )
    FIREBASE_SERVICE_ACCOUNT_PATH = ""
    for _p in _FIREBASE_SA_CANDIDATES:
        if _is_usable_firebase_service_account_file(_p):
            FIREBASE_SERVICE_ACCOUNT_PATH = str(_p.resolve())
            break

_FIREBASE_SA_SUPPLEMENT: dict = {}
if FIREBASE_SERVICE_ACCOUNT_PATH:
    _FIREBASE_SA_SUPPLEMENT = _parse_firebase_service_account_supplement(
        FIREBASE_SERVICE_ACCOUNT_PATH
    )

FIREBASE_PROJECT_ID = config("FIREBASE_PROJECT_ID", default="").strip()
if not FIREBASE_PROJECT_ID:
    FIREBASE_PROJECT_ID = (_FIREBASE_SA_SUPPLEMENT.get("project_id") or "").strip()

# Optional: entire service-account JSON as one line, or base64 of the JSON file (safer for \n in private_key).
FIREBASE_SERVICE_ACCOUNT_JSON = config(
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    default="",
).strip()
FIREBASE_SERVICE_ACCOUNT_B64 = config(
    "FIREBASE_SERVICE_ACCOUNT_B64",
    default="",
).strip()
# If True and no service-account file/dict: use GCP Application Default Credentials (Cloud Run/GCE).
# False by default so local dev fails fast with a clear “add JSON key” message instead of ADC errors.
FIREBASE_ALLOW_APPLICATION_DEFAULT_CREDENTIALS = config(
    "FIREBASE_ALLOW_APPLICATION_DEFAULT_CREDENTIALS",
    default=False,
    cast=bool,
)
