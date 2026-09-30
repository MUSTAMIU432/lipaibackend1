"""
Public web pages: the home page and the legal documents.

Google's OAuth consent screen (and the app stores) need a public home page,
privacy policy and terms of service on a domain the app owns. These are the
same documents the mobile app shows, generated from the app's
`src/lib/legal-docs.ts` by its `scripts/export-legal-pages.mjs` into
`legal_html/` — regenerate there after changing a document; never edit the
HTML here by hand, or the website and the app will disagree.

Set GOOGLE_SITE_VERIFICATION to the token Google Search Console gives for the
"HTML tag" method and every page carries the verification meta tag, so the
domain can be verified without a code change.
"""
from functools import lru_cache
from html import escape
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

PAGES_DIR = Path(__file__).resolve().parent / "legal_html"
PAGES = {"index", "terms", "privacy", "cookies", "payment-terms", "guidelines", "safety", "creator-program"}
_PLACEHOLDER = "{{GOOGLE_SITE_VERIFICATION}}"


@lru_cache(maxsize=None)
def _read(slug: str) -> str:
    return (PAGES_DIR / f"{slug}.html").read_text(encoding="utf-8")


def _page(slug: str) -> HttpResponse:
    if slug not in PAGES:
        raise Http404("No such page")
    token = (getattr(settings, "GOOGLE_SITE_VERIFICATION", "") or "").strip()
    meta = f'<meta name="google-site-verification" content="{escape(token)}">' if token else ""
    response = HttpResponse(_read(slug).replace(_PLACEHOLDER, meta), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_safe
def home(request):
    return _page("index")


@require_safe
def terms(request):
    return _page("terms")


@require_safe
def privacy(request):
    return _page("privacy")


@require_safe
def legal_page(request, slug: str):
    return _page(slug)
