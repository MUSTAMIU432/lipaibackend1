"""Normalize audience_type strings (single slug or |||-joined, max 3)."""

from __future__ import annotations

from typing import Optional

# Must match frontend `ONBOARDING_AUDIENCE_TYPES` values.
ONBOARDING_AUDIENCE_VALUES = frozenset(
    {
        "general",
        "teen",
        "young_adult",
        "adult",
        "adult_explicit",
        "educational",
        "professional",
        "fitness",
        "parenting",
        "senior",
    }
)

AUDIENCE_SEP = "|||"
MAX_AUDIENCE = 3


def normalize_audience_type_string(raw: Optional[str]) -> str:
    if not raw or not str(raw).strip():
        return "general"
    text = str(raw).strip()
    if AUDIENCE_SEP in text:
        parts = [p.strip() for p in text.split(AUDIENCE_SEP) if p.strip()]
    else:
        parts = [text]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p in ONBOARDING_AUDIENCE_VALUES and p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= MAX_AUDIENCE:
            break
    if not out:
        return "general"
    return AUDIENCE_SEP.join(out) if len(out) > 1 else out[0]
