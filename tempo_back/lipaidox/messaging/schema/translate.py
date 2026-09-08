"""Message translation — calls the Google Cloud Translate v2 REST API.

Requires `GOOGLE_TRANSLATE_API_KEY` (settings / env). There's no local
fallback: without a real key this raises rather than pretending to translate,
because a translate button that silently echoes the input back is worse than
one that visibly doesn't work yet.
"""
import requests
from django.conf import settings

from .types import DmTranslationType

_ENDPOINT = "https://translation.googleapis.com/language/translate/v2"


def translate_text(text: str, target_language: str) -> DmTranslationType:
    api_key = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", "") or ""
    if not api_key:
        raise Exception("Translation is not configured on this server.")

    try:
        resp = requests.post(
            _ENDPOINT,
            params={"key": api_key},
            json={"q": text, "target": target_language, "format": "text"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise Exception(f"Translation service unreachable: {exc}") from exc

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise Exception(f"Translation failed ({resp.status_code}){f': {detail}' if detail else ''}")

    data = resp.json()
    translations = data.get("data", {}).get("translations", [])
    if not translations:
        raise Exception("Translation returned no result.")

    first = translations[0]
    return DmTranslationType(
        translatedText=first.get("translatedText", ""),
        sourceLanguage=first.get("detectedSourceLanguage", ""),
        targetLanguage=target_language,
    )
