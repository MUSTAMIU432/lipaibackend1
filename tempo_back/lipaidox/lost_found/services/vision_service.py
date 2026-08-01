"""
Vision-LLM bridge for the /discover endpoint, backed by Groq's free tier
(https://console.groq.com/docs/rate-limits) running Llama 4 Scout, a
multimodal model with vision input + JSON mode support. Far more generous
free-tier quota than Gemini's 20 requests/day (Groq: 1,000 requests/day,
30/minute) for the same gap this module fills.

Some discover tabs (Search, AI Verify) need open-world image understanding that
no locally-installed model in this project provides (YOLOv8's ~80 generic
classes can't name a landmark/hotel/restaurant; there's no local AI-image
forensics model installed). The Price tab also needs an image->product-name
step before the real `price_compare_service` can run.

This module is the single connection point for those gaps. The key is read
straight from this project's `.env` via python-decouple's default `config`
singleton, which walks up from this file's directory until it finds the
`.env` next to manage.py — settings.py is intentionally left untouched.
Until GROK_API_KEY has a real value, `analyze_with_groq` returns None and
callers report the tab as a configured-but-not-connected gap rather than
fabricating data.
"""

import base64
import json
from io import BytesIO
from typing import Optional

from decouple import config

GROK_API_KEY = config("GROK_API_KEY", default="")
GROQ_MODEL = config("GROQ_MODEL", default="meta-llama/llama-4-scout-17b-16e-instruct")

PROMPTS = {
    "search": """You are a global image recognition and location intelligence engine. Analyze this image and identify the exact place, hotel, landmark, restaurant, or destination shown.

Be as specific and accurate as possible. If you recognize a famous location, provide real-world data.

If you cannot confidently identify the subject, set "name" to a short honest label (e.g. "Unidentified subject") describing what little can be said, and set every field you don't actually know — "rating", "reviews", "website", "phone", "email", "priceRange" — to JSON null. Never use an empty string "" or 0 as a substitute for "I don't know".

Respond ONLY with valid JSON matching this exact structure (no extra keys, no markdown):
{
  "type": "hotel"|"restaurant"|"landmark"|"product"|"destination"|"business",
  "name": "Exact name (e.g. Burj Khalifa, The Ritz London)",
  "description": "2-3 sentence factual description of the place",
  "location": "City, Country",
  "address": "Full street address if known",
  "coordinates": "25.1972° N, 55.2744° E",
  "category": "Category label (e.g. Iconic Tower, Luxury Hotel, Fine Dining)",
  "rating": 4.8,
  "reviews": 89450,
  "matchPercent": 98,
  "website": "www.burjkhalifa.ae",
  "phone": "+971 4 888 8888",
  "email": "info@example.com",
  "priceRange": "$$$",
  "hours": "Open Now • 10:00 AM – 12:00 AM",
  "nearbyAttractions": [
    { "name": "Dubai Mall", "type": "Shopping Center", "distance": "0.6 km" },
    { "name": "Dubai Fountain", "type": "Landmark", "distance": "0.7 km" },
    { "name": "Museum of the Future", "type": "Museum", "distance": "2.1 km" },
    { "name": "Dubai Opera", "type": "Venue", "distance": "1.3 km" }
  ]
}""",
    "verify": """You are an expert AI-generated content detector and digital forensics analyst. Analyze this image and determine if it is AI-generated, manipulated, or authentic.

Examine: texture patterns, lighting consistency, edge artifacts, noise distribution, color gradients, facial geometry (if present), known AI generator signatures (DALL-E, Midjourney, Stable Diffusion, etc.), and metadata characteristics.

Respond ONLY with valid JSON (no markdown, no extra keys):
{
  "isAI": true|false,
  "confidence": 92,
  "authenticityScore": 92,
  "generatorModel": null,
  "riskLevel": "Low"|"Medium"|"High",
  "verificationStatus": "Verified"|"Suspicious"|"Fake",
  "details": [
    { "label": "AI Manipulation", "value": "No manipulation detected", "status": "pass"|"fail"|"warning" },
    { "label": "Lighting Data", "value": "Consistent natural lighting", "status": "pass"|"fail"|"warning" },
    { "label": "Location Data", "value": "Consistent metadata", "status": "pass"|"fail"|"warning" },
    { "label": "Editing History", "value": "Trusted source – High visibility", "status": "pass"|"fail"|"warning" },
    { "label": "Source Analysis", "value": "platform.com by Author", "status": "pass"|"fail"|"warning" },
    { "label": "Noise Pattern", "value": "Natural photographic noise", "status": "pass"|"fail"|"warning" }
  ],
  "qualityMetrics": [
    { "label": "Sharpness", "value": 91 },
    { "label": "Reflections", "value": 78 },
    { "label": "Noise Level", "value": 85 },
    { "label": "Color Balance", "value": 94 },
    { "label": "Text Accuracy", "value": 70 },
    { "label": "Face Dimensions", "value": 88 }
  ],
  "originalSource": {
    "platform": "unsplash.com",
    "author": "Photographer Name",
    "url": "#"
  },
  "originalImages": [],
  "manipulatedAreas": []
}""",
    "price_naming": """You are a product recognition expert. Identify the exact product shown in this image so its price can be looked up.

Respond ONLY with valid JSON (no markdown, no extra keys):
{
  "productName": "Full product name with brand and model",
  "category": "Product category"
}""",
    "community_verdict": """You are analyzing content for a community verification platform. Provide a brief initial authenticity assessment that will be supplemented by community votes.

Respond ONLY with valid JSON (no markdown, no extra keys):
{
  "expert": "AI Preliminary Analysis",
  "verdict": "2-3 sentence initial assessment of authenticity based on visible characteristics",
  "confidence": 78
}""",
}


def _shrink_for_vision(file_bytes: bytes, max_dimension: int = 1568, max_bytes: int = 4 * 1024 * 1024) -> bytes:
    """Downscale/recompress to JPEG so the base64 payload stays under Groq's
    real-world request-size limit. Empirically Groq starts rejecting raw image
    bytes above ~8MB (413 request_too_large) well below its documented 4MB
    base64 cap — ordinary phone-camera JPEGs routinely exceed that. Vision
    models also gain nothing from resolution past ~1568px, so this is free.
    """
    from PIL import Image

    try:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return file_bytes

    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))

    quality = 85
    buf = BytesIO()
    while True:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes or quality <= 40:
            return buf.getvalue()
        quality -= 10


def _extract_video_frames(file_bytes: bytes, count: int = 5) -> list[bytes]:
    """Buffer the full video to a temp file and pull `count` evenly-spaced
    frames (as JPEG bytes) for deep multi-frame analysis, instead of judging
    a clip from a single midpoint frame. The temp file is the video's only
    on-disk presence — written once, read by every sampled seek, then removed
    once this extraction pass is done (there is no longer-lived session to
    keep it around for; each analyze call is a one-shot request).
    The Search/Verify file picker accepts video uploads, but Groq's vision API
    only accepts images — this lets video go through the same image pipeline
    instead of being rejected outright with 'invalid image data'.
    """
    import os
    import tempfile

    import cv2

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(file_bytes)
        tmp.close()
        cap = cv2.VideoCapture(tmp.name)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return []

        n = min(count, total)
        positions = [int(total * (i + 1) / (n + 1)) for i in range(n)]

        frames: list[bytes] = []
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                frames.append(buf.tobytes())
        cap.release()
        return frames
    finally:
        os.unlink(tmp.name)


def analyze_with_groq(file_bytes: bytes, mime_type: str, prompt_key: str, category: Optional[str] = None) -> Optional[dict]:
    """Run a vision prompt through Groq (Llama 4 Scout). Returns None if no API key is configured (the gap)."""
    if not GROK_API_KEY:
        return None

    from groq import Groq

    client = Groq(api_key=GROK_API_KEY)
    prompt = PROMPTS[prompt_key]

    if category and prompt_key == "search":
        prompt += (
            f'\n\nThe user tagged this upload as "{category}" before searching. Treat that as a strong '
            "hint about what to look for, but if the image clearly shows something else, identify what's "
            "actually there instead of forcing the wrong category."
        )

    image_blocks = []
    if (mime_type or "").startswith("video/"):
        frames = _extract_video_frames(file_bytes)
        if not frames:
            return None
        prompt += (
            "\n\nThe attached images are several frames sampled across one video clip "
            "(in chronological order), not separate unrelated photos. Use all of them "
            "together as evidence about the same subject before answering."
        )
        for frame in frames:
            shrunk = _shrink_for_vision(frame)
            b64 = base64.b64encode(shrunk).decode("utf-8")
            image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    else:
        if (mime_type or "").startswith("image/"):
            file_bytes = _shrink_for_vision(file_bytes)
            mime_type = "image/jpeg"
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        image_blocks.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64}"}})

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": prompt}, *image_blocks],
        }],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_completion_tokens=2000,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
