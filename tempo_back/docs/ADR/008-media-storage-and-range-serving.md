# ADR-008 — Off-box media storage and Range-aware serving

- **Status:** Accepted

## Context

The deploy host (Render) wipes its container filesystem on every restart/rebuild, so files
written under `MEDIA_ROOT` vanish while DB rows referencing them survive — the #1 cause of
"feed media won't play". Mobile `<video>` players also refuse to play unless the server
answers `Range` requests with `206 Partial Content`.

## Decision

- **Storage:** when `CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET` are all present, the REST
  upload endpoints stream files to **Cloudinary** and store the returned HTTPS URL
  (`settings.py:342-394`). Otherwise uploads fall back to `MEDIA_ROOT` (configurable to a
  persistent **Render Disk** mount); production warns loudly if `MEDIA_ROOT` is inside the
  app directory.
- **Serving:** `lipaidox_backend/urls.py` registers `ranged_media_serve` in **production
  too** (not only DEBUG) at `/media/`, implementing HTTP Range/206 with path-traversal
  guarding and DB-connection release before long streams (`lipaidox_backend/media_serve.py`).

## Consequences

- (+) Uploads survive redeploys (Cloudinary or disk); videos seek/buffer on mobile.
- (+) Config decoupled — local dev keeps working without a Cloudinary account.
- (-) Cloudinary free-tier caps apply (10 MB image, 100 MB video).
- (-) Serving media from the app process couples bandwidth to app workers; a CDN could
  front Cloudinary behind `/media/` later.