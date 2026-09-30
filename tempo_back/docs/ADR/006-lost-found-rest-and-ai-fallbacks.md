# ADR-006 — Lost & Found exposed as REST with graceful AI fallbacks

- **Status:** Accepted

## Context

The Discover/Lost & Found feature performs heavy AI work (visual search, AI/deepfake
detection, QR scanning, price comparison, Gemini/Groq vision, Google Places, Wikimedia) with
expensive models and rate-limited external APIs. GraphQL-first (ADR-001) is the norm, but
these flows are upload/response oriented, time-sensitive, and must degrade gracefully.

## Decision

- Expose Lost & Found AI features as a **REST API mounted at the URL root**
  (`lipaidox/lost_found/urls.py`) — the deliberate exception to GraphQL-first. Community
  features (polls, Q&A) stay on GraphQL alongside it.
- Every service (`lipaidox/lost_found/services/`) **degrades to fallbacks** when models or
  API keys are unavailable (local reverse search, ELA/noise/frequency analysis, OpenCV,
  requests+BeautifulSoup).
- `discover_adapters.py` reshapes raw service output into the exact TypeScript shapes the
  frontend `/discover` page expects; unusable results return `None` so views report a gap
  rather than forwarding errors/empty data.

## Consequences

- (+) Simple multipart uploads and streaming responses for media-heavy AI.
- (+) Frontend contract is explicit and stable via adapters; outages degrade to gaps.
- (-) Two API paradigms must be documented for clients (see `docs/API.md`).
- (-) REST surface duplicates RBAC/auth handling that GraphQL centralizes.
- (-) Model downloads (CLIP ~2GB + YOLOv8 + Faiss) are heavy for the app process — model
  lifecycle belongs in the future Celery/broker plan.