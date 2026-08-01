"""
Real photos of a named place — two-stage strategy:

  1. Wikipedia page media list  (works for famous landmarks, cities, etc.)
  2. Wikimedia Commons image search  (broader, works for hotels/businesses
     that don't have their own Wikipedia article)

Both are free and keyless. Returns [] when nothing is found so callers
never fabricate a count or filler image.
"""

from urllib.parse import quote

import requests

_HEADERS = {
    "User-Agent": "Lipaidox-Discover/1.0 (https://lipaidox.com; discover-search-photos)"
}
_TIMEOUT = 5


def _wikipedia_page_photos(name: str, limit: int) -> list[str]:
    """Photos from a Wikipedia page's media list. Returns [] on 404."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/media-list/{quote(name)}"
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return []
        urls: list[str] = []
        for item in resp.json().get("items", []):
            if item.get("type") != "image" or not item.get("srcset"):
                continue
            src = item["srcset"][-1]["src"]
            if not src.lower().split("?")[0].endswith((".jpg", ".jpeg")):
                continue
            urls.append(f"https:{src}" if src.startswith("//") else src)
            if len(urls) >= limit:
                break
        return urls
    except Exception:
        return []


def _commons_search_photos(query: str, limit: int) -> list[str]:
    """
    Wikimedia Commons file search — finds photos even when there's no
    dedicated Wikipedia article. Fetches image URLs in a second call.
    """
    try:
        # Step 1: search for matching file titles
        search_resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            headers=_HEADERS,
            params={
                "action":      "query",
                "list":        "search",
                "srsearch":    query,
                "srnamespace": "6",       # File: namespace
                "srlimit":     str(limit * 2),
                "format":      "json",
            },
            timeout=_TIMEOUT,
        )
        search_resp.raise_for_status()
        hits = search_resp.json().get("query", {}).get("search", [])
        if not hits:
            return []

        # Filter to jpg/jpeg titles only before fetching URLs
        titles = [
            h["title"] for h in hits
            if h.get("title", "").lower().endswith((".jpg", ".jpeg"))
        ][:limit]
        if not titles:
            return []

        # Step 2: resolve file titles → direct image URLs
        info_resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            headers=_HEADERS,
            params={
                "action":  "query",
                "titles":  "|".join(titles),
                "prop":    "imageinfo",
                "iiprop":  "url",
                "iiurlwidth": "800",
                "format":  "json",
            },
            timeout=_TIMEOUT,
        )
        info_resp.raise_for_status()
        pages = info_resp.json().get("query", {}).get("pages", {})
        urls: list[str] = []
        for page in pages.values():
            for ii in page.get("imageinfo", []):
                u = ii.get("thumburl") or ii.get("url", "")
                if u:
                    urls.append(u)
                    if len(urls) >= limit:
                        return urls
        return urls
    except Exception:
        return []


def fetch_place_photos(name: str, limit: int = 8) -> list[str]:
    """
    Return up to `limit` real JPEG photo URLs for `name`.
    Tries Wikipedia first (better quality match), then Wikimedia Commons.
    """
    if not name:
        return []

    photos = _wikipedia_page_photos(name, limit)
    if photos:
        return photos

    return _commons_search_photos(name, limit)
