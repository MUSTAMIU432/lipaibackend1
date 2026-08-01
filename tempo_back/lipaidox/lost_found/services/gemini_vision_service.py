"""
Gemini Vision service for the /discover Search tab.

Uses the GEMINI_API_KEY from .env (google.generativeai SDK already installed
in this venv). Accepts the same image bytes + prompt key contract as
vision_service.py so discover_views.py can swap them transparently.

Falls back gracefully: returns None if the key is missing or the call fails,
letting the caller try Groq next.
"""

import base64
import json
from io import BytesIO
from typing import Optional

from decouple import config

GEMINI_API_KEY = config("GEMINI_API_KEY", default="").strip()
GEMINI_MODEL   = config("GEMINI_MODEL", default="gemini-1.5-flash")

# Reuse the same search prompt from vision_service so behaviour is identical
SEARCH_PROMPT = """You are a global image recognition and location intelligence engine. Analyze this image and identify the exact place, hotel, landmark, restaurant, or destination shown.

Be as specific and accurate as possible. If you recognize a famous location, provide real-world data.

If you cannot confidently identify the subject, set "name" to a short honest label (e.g. "Unidentified subject") and every field you don't actually know to JSON null. Never use "" or 0 as a substitute for null.

Respond ONLY with valid JSON matching this exact structure (no extra keys, no markdown):
{
  "type": "hotel"|"restaurant"|"landmark"|"product"|"destination"|"business",
  "name": "Exact name",
  "description": "2-3 sentence factual description",
  "location": "City, Country",
  "address": "Full street address if known",
  "coordinates": "lat° N, lng° E",
  "category": "Category label",
  "rating": 4.8,
  "reviews": 89450,
  "matchPercent": 98,
  "website": "www.example.com",
  "phone": "+1 234 567 8900",
  "email": null,
  "priceRange": "$$$",
  "hours": "Open Now • 10:00 AM – 12:00 AM",
  "nearbyAttractions": [
    { "name": "Nearby Place", "type": "Type", "distance": "0.5 km" }
  ]
}"""


def _shrink(file_bytes: bytes, max_dim: int = 1568, max_bytes: int = 4 * 1024 * 1024) -> bytes:
    from PIL import Image
    try:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return file_bytes
    if max(img.size) > max_dim:
        r = max_dim / max(img.size)
        img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))))
    quality = 85
    buf = BytesIO()
    while True:
        buf.seek(0); buf.truncate()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes or quality <= 40:
            return buf.getvalue()
        quality -= 10


def analyze_with_gemini(
    file_bytes: bytes,
    mime_type: str,
    category: Optional[str] = None,
) -> Optional[dict]:
    """
    Run Gemini Vision on the image and return a parsed JSON dict.
    Returns None if the key is absent or the call fails.
    """
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        return None

    prompt = SEARCH_PROMPT
    if category:
        prompt += (
            f'\n\nThe user tagged this image as "{category}". '
            "Use that as a strong hint but identify what is actually shown."
        )

    # Shrink image so we stay inside Gemini's inline-data size limit
    if (mime_type or "").startswith("image/"):
        file_bytes = _shrink(file_bytes)
        mime_type = "image/jpeg"

    image_part = {
        "inline_data": {
            "mime_type": mime_type or "image/jpeg",
            "data": base64.b64encode(file_bytes).decode("utf-8"),
        }
    }

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            [prompt, image_part],
            generation_config={"temperature": 0.1, "max_output_tokens": 2000},
        )
        raw = response.text or "{}"
        # Strip markdown fences if the model added them
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return None
