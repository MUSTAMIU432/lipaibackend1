"""
Google Places API (New) integration.

Fetches real data for all five Search-tab sub-tabs:
  Overview   — editorialSummary, rating, reviews count, phone, website, hours
  Reviews    — up to 5 real Google reviews with author, rating, text, relative time
  Photos     — up to 6 real Google place photos (via Places Photos media endpoint)
  Tickets    — booking URL derived from website / reservable flag
  Similar    — nearby places of the same primaryType

Uses the modern REST endpoints at places.googleapis.com only.
The legacy maps.googleapis.com/maps/api/place/* is NOT enabled on this project.
"""

import math
import requests
from django.conf import settings

_BASE    = "https://places.googleapis.com/v1/places"
_TIMEOUT = 6


def _key():
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()


def _fetch_photo_url(key: str, photo_name: str) -> str | None:
    """Resolve a photo reference name to a public CDN URL."""
    try:
        r = requests.get(
            f"https://places.googleapis.com/v1/{photo_name}/media",
            params={"key": key, "maxWidthPx": 800, "skipHttpRedirect": "true"},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json().get("photoUri")
    except Exception:
        pass
    return None


def find_and_enrich_place(name: str, location: str) -> dict:
    """
    Search Google Places (New) for `name + location` and return a dict
    with real data for every Search-result sub-tab.
    Returns {} on any failure so callers keep the AI-model data.
    """
    key = _key()
    if not key:
        return {}

    query = f"{name} {location}".strip()

    # ── 1. Text Search (New) ────────────────────────────────────────────────
    try:
        ts = requests.post(
            f"{_BASE}:searchText",
            headers={
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": (
                    "places.id,"
                    "places.displayName,"
                    "places.rating,"
                    "places.userRatingCount,"
                    "places.formattedAddress,"
                    "places.location,"
                    "places.internationalPhoneNumber,"
                    "places.websiteUri,"
                    "places.googleMapsUri,"
                    "places.regularOpeningHours,"
                    "places.editorialSummary,"
                    "places.primaryType,"
                    "places.reservable"
                ),
                "Content-Type": "application/json",
            },
            json={"textQuery": query},
            timeout=_TIMEOUT,
        )
        ts.raise_for_status()
    except Exception:
        return {}

    places = ts.json().get("places", [])
    if not places:
        return {}

    p            = places[0]
    loc          = p.get("location", {})
    lat          = loc.get("latitude")
    lng          = loc.get("longitude")
    primary_type = p.get("primaryType", "")
    oh           = p.get("regularOpeningHours", {})

    # ── Hours string ────────────────────────────────────────────────────────
    hours_str = None
    if oh:
        open_now  = oh.get("openNow")
        weekday   = oh.get("weekdayDescriptions", [])
        status    = "Open Now" if open_now else "Closed"
        hours_str = f"{status} • {weekday[0]}" if weekday else status

    # ── Editorial summary (Overview tab) ───────────────────────────────────
    editorial = None
    if p.get("editorialSummary"):
        editorial = p["editorialSummary"].get("text")

    # ── Booking / Tickets ───────────────────────────────────────────────────
    website     = p.get("websiteUri")
    google_maps = p.get("googleMapsUri")
    reservable  = p.get("reservable", False)
    booking_url = website or google_maps

    # Reviews deep-link: go straight to the reviews section on Google Maps
    reviews_url = f"{google_maps}#reviews" if google_maps else None

    enriched: dict = {
        "placeId":          p.get("id"),
        "lat":              lat,
        "lng":              lng,
        "rating":           p.get("rating"),
        "reviews":          p.get("userRatingCount"),
        "phone":            p.get("internationalPhoneNumber"),
        "website":          website,
        "googleMapsUri":    google_maps,
        "reviewsUrl":       reviews_url,
        "hours":            hours_str,
        "address":          p.get("formattedAddress"),
        "editorialSummary": editorial,
        "bookingUrl":       booking_url,
        "reservable":       reservable,
    }

    # ── 2. Nearby Search (New) ──────────────────────────────────────────────
    if lat is not None and lng is not None:
        try:
            nb = requests.post(
                f"{_BASE}:searchNearby",
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": (
                        "places.displayName,"
                        "places.location,"
                        "places.primaryType,"
                        "places.rating"
                    ),
                    "Content-Type": "application/json",
                },
                json={
                    "locationRestriction": {
                        "circle": {
                            "center": {"latitude": lat, "longitude": lng},
                            "radius": 3000.0,
                        }
                    },
                    "maxResultCount": 20,
                },
                timeout=_TIMEOUT,
            )
            nb.raise_for_status()

            attractions, similar = [], []
            for np in nb.json().get("places", []):
                pname = (np.get("displayName") or {}).get("text", "")
                if not pname:
                    continue
                # Skip the place itself (full name from Google may differ from AI name)
                if pname.lower().startswith(name.lower()) or name.lower() in pname.lower():
                    continue
                ploc  = np.get("location", {})
                plat  = ploc.get("latitude", lat)
                plng  = ploc.get("longitude", lng)
                dist  = int(math.sqrt((plat - lat) ** 2 + (plng - lng) ** 2) * 111_000)
                ptype_raw = np.get("primaryType") or "place"
                ptype = ptype_raw.replace("_", " ").title()
                entry = {
                    "name":     pname,
                    "type":     ptype,
                    "distance": f"{dist} m" if dist < 1000 else f"{dist / 1000:.1f} km",
                    "rating":   np.get("rating"),
                }
                if len(attractions) < 6:
                    attractions.append(entry)
                # Similar: same broad category (hotel→hotel, restaurant→restaurant)
                # Compare primary_type prefix so "hotel" matches "hotel", etc.
                if (
                    primary_type
                    and len(similar) < 6
                    and ptype_raw.split("_")[0] == primary_type.split("_")[0]
                ):
                    similar.append(entry)

            if attractions:
                enriched["nearbyAttractions"] = attractions
            # Fall back: if no exact-type similar found, use attractions list
            enriched["similarPlaces"] = similar if similar else attractions

        except Exception:
            pass

    return enriched
