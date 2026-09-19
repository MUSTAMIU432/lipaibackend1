"""Word limits for written (text) posts — mirrors `wordLimitFor` in the mobile app."""
from __future__ import annotations

NORMAL_WORD_LIMIT = 200
CUSTOM_WORD_LIMIT = 100


def is_customized(style) -> bool:
    """A post is 'customized' once it has a background (colour or image)."""
    if not isinstance(style, dict):
        return False
    if style.get("backgroundImage"):
        return True
    background = style.get("backgroundId")
    return background not in (None, "", "none")


def word_limit_for(style) -> int:
    return CUSTOM_WORD_LIMIT if is_customized(style) else NORMAL_WORD_LIMIT


def assert_text_post_within_limit(text, style) -> None:
    words = len((text or "").split())
    limit = word_limit_for(style)
    if words > limit:
        detail = " with a background" if limit == CUSTOM_WORD_LIMIT else ""
        raise Exception(f"Text posts are limited to {limit} words{detail}; yours has {words}.")
