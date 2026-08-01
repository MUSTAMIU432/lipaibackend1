"""
Backend for the frontend's /discover page (6 tabs: Search, AI Verify, QR Scan,
Price, Deepfake, Community). Single endpoint mirrors the existing frontend
request contract: POST {tab, fileBase64, mediaType} -> {success, tab, result}.

QR / Deepfake / Community are wired to real `lost_found` AI services. Search,
Verify, and Price (which needs an image->product-name step first) depend on
a vision LLM call (`services.vision_service`, backed by Groq's free tier
running Llama 4 Scout) that is a real connection point but returns None until
GROK_API_KEY is set in `.env` — those tabs report a gap rather than
fabricating data; the frontend already falls back to its own mock/demo data
whenever the indicator field is missing.
"""

import base64
import os
import tempfile
from io import BytesIO

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..discover_adapters import adapt_community, adapt_deepfake, adapt_price, adapt_qr
from ..models.lost_found import LostFoundItem
from ..services import get_community_service, get_deepfake_service, get_price_compare_service, get_qr_scanner_service
from ..services.vision_service import analyze_with_groq
from ..services.gemini_vision_service import analyze_with_gemini
from ..services.wikimedia_service import fetch_place_photos
from ..services.places_service import find_and_enrich_place

GAP_NO_VISION_KEY = "GROK_API_KEY not configured — set it in .env to connect this tab to a live vision model"


class _TempPathFile(str):
    """A str subclass so `cv2.imread(str(image_file))` resolves to a real path,
    while still exposing `.content_type` for code that expects an upload-like object."""

    def __new__(cls, path, content_type):
        obj = super().__new__(cls, path)
        obj.content_type = content_type
        return obj


@api_view(["POST"])
@permission_classes([AllowAny])
def discover_analyze(request):
    tab = request.data.get("tab")
    file_b64 = request.data.get("fileBase64")
    media_type = request.data.get("mediaType", "image/jpeg")
    category = request.data.get("category")

    if not tab or not file_b64:
        return Response({"error": "Missing required fields"}, status=400)

    try:
        file_bytes = base64.b64decode(file_b64)
    except (ValueError, TypeError):
        return Response({"error": "Invalid fileBase64"}, status=400)

    handlers = {
        "search": _handle_llm_tab,
        "verify": _handle_llm_tab,
        "qr": _handle_qr,
        "price": _handle_price,
        "deepfake": _handle_deepfake,
        "community": _handle_community,
    }
    handler = handlers.get(tab)
    if handler is None:
        return Response({"error": "Invalid tab"}, status=400)

    try:
        result, gap = handler(tab, file_bytes, media_type, category)
    except Exception as exc:
        return Response({"success": False, "tab": tab, "result": {}, "error": str(exc)})

    if result is None:
        return Response({"success": False, "tab": tab, "result": {}, "gap": gap or "analysis failed"})
    return Response({"success": True, "tab": tab, "result": result})


def _handle_llm_tab(tab, file_bytes, media_type, category=None):
    # ── Search tab: Gemini Vision first, Groq as fallback ──────────────────
    if tab == "search":
        result = analyze_with_gemini(file_bytes, media_type, category=category)
        if result is None:
            result = analyze_with_groq(file_bytes, media_type, tab, category=category)
        if result is None:
            return None, "Neither GEMINI_API_KEY nor GROK_API_KEY produced a result — check .env"

        if result.get("name"):
            # Wikipedia photos (free, keyless)
            result["photos"] = fetch_place_photos(result["name"])

            # Google Places API: real rating, reviews, phone, website, hours,
            # precise lat/lng, place_id, and real nearby attractions
            enriched = find_and_enrich_place(
                result.get("name", ""),
                result.get("location", ""),
            )
            if enriched:
                # Scalar fields — only override when Google has a real value
                for field in (
                    "rating", "reviews", "phone", "website", "hours",
                    "address", "placeId", "lat", "lng",
                    "editorialSummary", "bookingUrl", "googleMapsUri",
                    "reviewsUrl", "reservable",
                ):
                    if enriched.get(field) is not None:
                        result[field] = enriched[field]
                # List fields — only attach when non-empty
                for field in ("nearbyAttractions", "similarPlaces"):
                    if enriched.get(field):
                        result[field] = enriched[field]

        return result, None

    # ── All other tabs: Groq only ───────────────────────────────────────────
    result = analyze_with_groq(file_bytes, media_type, tab, category=category)
    if result is None:
        return None, GAP_NO_VISION_KEY
    return result, None


def _handle_qr(tab, file_bytes, media_type, category=None):
    raw = get_qr_scanner_service().scan_image(BytesIO(file_bytes))
    return adapt_qr(raw), None


def _handle_price(tab, file_bytes, media_type, category=None):
    naming = analyze_with_groq(file_bytes, media_type, "price_naming")
    if not naming or not naming.get("productName"):
        return None, GAP_NO_VISION_KEY + " (needed to identify the product from the image first)"

    product_name = naming["productName"]
    product_category = naming.get("category", "")
    raw = get_price_compare_service().compare_prices(product_name)
    result = adapt_price(raw, product_name, product_category)
    if result is None:
        return None, "no price sources returned results for this product"
    return result, None


def _handle_deepfake(tab, file_bytes, media_type, category=None):
    suffix = ".mp4" if media_type.startswith("video/") else ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file_bytes)
        tmp.close()
        media_file = _TempPathFile(tmp.name, media_type)
        raw = get_deepfake_service().analyze_media(media_file)
    finally:
        os.unlink(tmp.name)

    result = adapt_deepfake(raw)
    if result is None:
        return None, raw.get("message", "deepfake analysis failed")
    return result, None


def _handle_community(tab, file_bytes, media_type, category=None):
    item = LostFoundItem.objects.create(
        title=f"Discover submission {timezone.now().isoformat()}",
        category="other",
        status="found",
        reporter=None,
    )
    consensus = get_community_service().get_item_consensus(str(item.id))
    expert_verdict = analyze_with_groq(file_bytes, media_type, "community_verdict")
    return adapt_community(consensus, expert_verdict), None


@api_view(["POST"])
@permission_classes([AllowAny])
def discover_similar_place(request):
    """
    Fetch full place details for a Similar Places card click.
    POST body: { "name": "...", "location": "..." }
    Returns a SearchResult-shaped dict for the frontend to display directly.
    """
    name     = (request.data.get("name") or "").strip()
    location = (request.data.get("location") or "").strip()
    if not name:
        return Response({"error": "name is required"}, status=400)

    enriched = find_and_enrich_place(name, location)
    photos   = fetch_place_photos(name)

    lat = enriched.get("lat")
    lng = enriched.get("lng")
    coords = (
        f"{lat:.4f}° {'N' if lat >= 0 else 'S'}, {abs(lng):.4f}° {'E' if lng >= 0 else 'W'}"
        if lat is not None and lng is not None else None
    )

    result = {
        "type":             "destination",
        "name":             name,
        "description":      enriched.get("editorialSummary") or f"{name} — a notable place in {location}.",
        "location":         location or enriched.get("address", ""),
        "address":          enriched.get("address", ""),
        "category":         location or "Place",
        "rating":           enriched.get("rating"),
        "reviews":          enriched.get("reviews"),
        "website":          enriched.get("website"),
        "phone":            enriched.get("phone"),
        "email":            None,
        "priceRange":       None,
        "hours":            enriched.get("hours"),
        "coordinates":      coords,
        "photos":           photos,
        "placeId":          enriched.get("placeId"),
        "lat":              lat,
        "lng":              lng,
        "editorialSummary": enriched.get("editorialSummary"),
        "bookingUrl":       enriched.get("bookingUrl"),
        "reservable":       enriched.get("reservable", False),
        "googleMapsUri":    enriched.get("googleMapsUri"),
        "reviewsUrl":       enriched.get("reviewsUrl"),
        "nearbyAttractions": enriched.get("nearbyAttractions", []),
        "similarPlaces":    enriched.get("similarPlaces", []),
        "matchPercent":     None,
    }

    return Response({"success": True, "result": result})
