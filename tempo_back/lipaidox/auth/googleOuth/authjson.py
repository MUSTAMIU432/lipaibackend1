"""
Firebase **service account** material for Admin SDK.

**Never commit** real private keys to git. Supported sources (see ``load_firebase_service_account_dict``), in order:

1. ``INLINE_FIREBASE_SERVICE_ACCOUNT`` — dict in **this file** (same keys as the JSON download). Leave ``None`` in shared branches.
2. ``authjson_secrets.py`` — optional sibling module (gitignored) defining ``FIREBASE_SERVICE_ACCOUNT`` dict.
3. ``FIREBASE_SERVICE_ACCOUNT_B64`` / ``FIREBASE_SERVICE_ACCOUNT_JSON`` in Django settings (``.env``).
4. JSON files in ``lipaidox/auth/googleOuth/`` next to ``authjson.py`` (e.g. ``firebase-service-account.json``).
5. ``firebase-service-account.json`` (or ``secrets/firebase-service-account.json``) under Django ``BASE_DIR`` (e.g. ``tempo_back/``).

``googleOuth`` loads **this module first**, then ``FIREBASE_SERVICE_ACCOUNT_PATH`` in ``googleOuth.py`` if still needed.

Generate B64 (once) after downloading the key::

    base64 -w0 your-service-account.json
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parent
_LOCAL_CREDENTIAL_FILES = (
    "firebase-service-account.json",
    "firebase-service-account.local.json",
    "serviceAccount.local.json",
    "authjson.local.json",
    "authjson.json",
)

# Assign your Firebase service account dict here for local dev only (same structure as the
# downloaded JSON). Must remain ``None`` in version control — use ``authjson_secrets.py`` or a
# ``.local.json`` file if you prefer not to touch this variable.
INLINE_FIREBASE_SERVICE_ACCOUNT: dict[str, Any] | None = None


def validate_service_account_dict(data: Any, source: str) -> dict | None:
    """Return ``data`` if it matches a Firebase/GCP service account JSON (Admin SDK), else None."""
    if not isinstance(data, dict):
        logger.error("Firebase credential from %s must be a JSON object.", source)
        return None
    required = ("type", "project_id", "private_key", "client_email")
    missing = [k for k in required if not data.get(k)]
    if missing:
        logger.error(
            "Firebase service account from %s is missing keys: %s",
            source,
            ", ".join(missing),
        )
        return None
    if data.get("type") != "service_account":
        logger.error("Firebase credential from %s: expected type 'service_account'.", source)
        return None
    return data


def _try_load_json_file(path: Path) -> dict | None:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.exception("Failed to read Firebase service account file %s", path)
        return None
    validated = validate_service_account_dict(data, str(path))
    if validated:
        logger.info("Loaded Firebase service account from %s", path)
        return validated
    logger.warning("Skipping invalid service account file: %s", path)
    return None


def _load_from_local_files() -> dict | None:
    """Load first valid JSON in ``googleOuth/`` (same directory as this module)."""
    tried: set[Path] = set()
    for name in _LOCAL_CREDENTIAL_FILES:
        path = (_DIR / name).resolve()
        if not path.is_file():
            continue
        tried.add(path)
        got = _try_load_json_file(path)
        if got:
            return got
    # e.g. lipaidox-platform-firebase-adminsdk-xxxxx.json (default download name)
    for path in sorted(_DIR.glob("*.json"), key=lambda p: p.name):
        rp = path.resolve()
        if rp in tried:
            continue
        got = _try_load_json_file(path)
        if got:
            return got
    return None


def _load_from_django_base_dir() -> dict | None:
    """Load ``firebase-service-account.json`` from Django ``BASE_DIR`` (project root, e.g. ``tempo_back/``)."""
    try:
        from django.conf import settings

        base = getattr(settings, "BASE_DIR", None)
        if not base:
            return None
        base_path = Path(base).resolve()
        for rel in (
            "firebase-service-account.json",
            Path("secrets") / "firebase-service-account.json",
        ):
            path = (base_path / rel).resolve()
            if not path.is_file():
                continue
            got = _try_load_json_file(path)
            if got:
                return got
    except Exception:
        logger.exception("Failed loading Firebase service account from BASE_DIR.")
    return None


def _load_from_secrets_module() -> dict | None:
    try:
        from . import authjson_secrets
    except ImportError:
        return None
    raw = getattr(authjson_secrets, "FIREBASE_SERVICE_ACCOUNT", None)
    if raw is None:
        raw = getattr(authjson_secrets, "SERVICE_ACCOUNT", None)
    if not raw:
        return None
    validated = validate_service_account_dict(raw, "authjson_secrets.py")
    if validated:
        logger.info("Loaded Firebase service account from authjson_secrets.py.")
    return validated


def load_firebase_service_account_dict() -> dict | None:
    """
    Return a dict for ``firebase_admin.credentials.Certificate``, or ``None``.

    Order: ``INLINE_FIREBASE_SERVICE_ACCOUNT``, ``authjson_secrets`` module, Django B64/JSON,
    then local JSON files beside this module.
    """
    if INLINE_FIREBASE_SERVICE_ACCOUNT is not None:
        validated = validate_service_account_dict(
            INLINE_FIREBASE_SERVICE_ACCOUNT,
            "authjson.INLINE_FIREBASE_SERVICE_ACCOUNT",
        )
        if validated:
            logger.info(
                "Loaded Firebase service account from INLINE_FIREBASE_SERVICE_ACCOUNT in authjson.py."
            )
            return validated
        logger.warning(
            "INLINE_FIREBASE_SERVICE_ACCOUNT is set but invalid; trying env / local JSON files."
        )

    from_secrets = _load_from_secrets_module()
    if from_secrets is not None:
        return from_secrets

    # Prefer on-disk JSON next to this module, then project root (BASE_DIR), before .env B64/JSON.
    from_disk = _load_from_local_files()
    if from_disk is not None:
        return from_disk

    from_base = _load_from_django_base_dir()
    if from_base is not None:
        return from_base

    from django.conf import settings

    b64 = (getattr(settings, "FIREBASE_SERVICE_ACCOUNT_B64", None) or "").strip()
    if b64:
        try:
            raw = base64.b64decode(b64, validate=True)
            data = json.loads(raw.decode("utf-8"))
            validated = validate_service_account_dict(data, "FIREBASE_SERVICE_ACCOUNT_B64")
            if validated:
                logger.info("Loaded Firebase service account from FIREBASE_SERVICE_ACCOUNT_B64.")
                return validated
            logger.warning(
                "FIREBASE_SERVICE_ACCOUNT_B64 decodes but is not a valid service account; "
                "no other credential source matched."
            )
        except Exception as e:
            logger.warning(
                "FIREBASE_SERVICE_ACCOUNT_B64 is invalid (%s); ensure firebase-service-account.json "
                "is next to authjson.py or fix .env.",
                e,
            )

    inline = (getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", None) or "").strip()
    if inline:
        try:
            data = json.loads(inline)
            validated = validate_service_account_dict(data, "FIREBASE_SERVICE_ACCOUNT_JSON")
            if validated:
                logger.info("Loaded Firebase service account from FIREBASE_SERVICE_ACCOUNT_JSON.")
                return validated
            logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON is not a valid service account dict.")
        except Exception as e:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON parse error: %s", e)

    return None


def credential_lookup_hint() -> str:
    """Where the backend looks for the Firebase service account (for error messages / DEBUG)."""
    lines: list[str] = []
    for name in _LOCAL_CREDENTIAL_FILES:
        p = (_DIR / name).resolve()
        exists = "exists" if p.is_file() else "missing"
        lines.append(f"{p} ({exists})")
    try:
        from django.conf import settings

        base = Path(getattr(settings, "BASE_DIR", "") or "")
        env_path = (getattr(settings, "FIREBASE_SERVICE_ACCOUNT_PATH", None) or "").strip()
        if env_path:
            ep = Path(env_path).expanduser().resolve()
            st = "exists" if ep.is_file() else "missing"
            lines.append(f"{ep} ({st}) [FIREBASE_SERVICE_ACCOUNT_PATH]")
        if base:
            for rel in ("firebase-service-account.json", "secrets/firebase-service-account.json"):
                p = (base / rel).resolve()
                st = "exists" if p.is_file() else "missing"
                lines.append(f"{p} ({st}) [BASE_DIR]")
    except Exception:
        pass
    return "Credential search: " + "; ".join(lines)
