"""
Upload user media to Cloudinary and describe the stored asset.

Render's container filesystem is ephemeral: anything written under MEDIA_ROOT is
gone on the next restart while the database row that points at it survives, which
is what turns a feed into posts whose media "won't play". This module is the one
place that puts uploaded bytes somewhere permanent and hands back the HTTPS URL
to store instead.

Callers stay unaware of Cloudinary's SDK: they pass a Django ``UploadedFile`` and
get an :class:`UploadResult`, or a :class:`CloudinaryUploadError` they can turn
into an HTTP response. When credentials are absent (`CLOUDINARY_ENABLED` is
False) the caller is expected to fall back to local disk, so local development
and CI keep working without a Cloudinary account.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# Videos above this are sent with Cloudinary's chunked endpoint. The normal
# upload buffers the whole body, which is what makes a large upload die as a
# worker timeout or a reset connection rather than a clean error.
LARGE_UPLOAD_THRESHOLD_BYTES = 90 * 1024 * 1024
CHUNK_SIZE_BYTES = 20 * 1024 * 1024

# Seconds. A stalled upload must fail as a 502 we can explain, not hang the
# worker until the platform kills it.
UPLOAD_TIMEOUT_SECONDS = 180


class CloudinaryUploadError(Exception):
    """
    A media upload could not be stored.

    ``status_code`` is the HTTP status the API should answer with, and the
    message is safe to show a client: it never carries credentials or a
    stack trace.
    """

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class UploadResult:
    """What Cloudinary stored, in the shape callers persist."""

    secure_url: str
    public_id: str
    resource_type: str
    format: str | None = None
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    duration: float | None = None


def is_enabled() -> bool:
    """True when credentials are configured and uploads should go to Cloudinary."""
    return bool(getattr(settings, "CLOUDINARY_ENABLED", False))


def resource_type_for(content_type: str) -> str:
    """
    Cloudinary's resource_type for a MIME type.

    Video and image get their own types so Cloudinary transcodes and serves them
    correctly; everything else (PDF, zip, audio) is ``raw``, which stores bytes
    untouched. Audio is deliberately *not* ``video``: Cloudinary accepts audio
    under the video type, but that opts the file into transcoding we do not want
    for voice notes.
    """
    ct = (content_type or "").strip().lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    return "raw"


def _folder_for(domain: str, user_id: Any) -> str:
    """
    Folder path for an upload, mirroring the local layout it replaces.

    e.g. ``lipaidox/content/42`` — the same ``<domain>/<user id>`` split the
    MEDIA_ROOT implementation used, so assets stay attributable per uploader.
    """
    prefix = getattr(settings, "CLOUDINARY_FOLDER", "lipaidox") or "lipaidox"
    return f"{prefix}/{domain}/{user_id}"


def upload_file(
    file,
    *,
    domain: str,
    user_id: Any,
    content_type: str = "",
    public_id: str | None = None,
    private: bool = False,
) -> UploadResult:
    """
    Store ``file`` on Cloudinary and return where it landed.

    ``domain`` is the media domain ("profiles", "content", ...) and becomes part
    of the Cloudinary folder. Raises :class:`CloudinaryUploadError` for every
    failure, so callers never see an SDK exception.

    ``private=True`` stores the asset with ``type="authenticated"``, so its URL
    only resolves when signed. Identity documents and selfies (KYC) must use it:
    a default upload is world-readable to anyone holding the URL.
    """
    if not is_enabled():
        raise CloudinaryUploadError(
            "Media storage is not configured on this server.", status_code=503
        )

    # Imported lazily so the module is importable (and testable) without the
    # dependency installed, and so settings.py owns configuration.
    import cloudinary.uploader

    resource_type = resource_type_for(content_type)
    options: dict[str, Any] = {
        "folder": _folder_for(domain, user_id),
        "resource_type": resource_type,
        # Let Cloudinary derive the public id unless the caller wants a stable
        # one; random ids avoid collisions between identically named uploads.
        "unique_filename": True,
        "overwrite": False,
        "timeout": UPLOAD_TIMEOUT_SECONDS,
    }
    if public_id:
        options["public_id"] = public_id
        options["unique_filename"] = False
    if private:
        options["type"] = "authenticated"

    size = getattr(file, "size", 0) or 0
    use_chunked = resource_type == "video" and size > LARGE_UPLOAD_THRESHOLD_BYTES

    try:
        if use_chunked:
            options["chunk_size"] = CHUNK_SIZE_BYTES
            payload = cloudinary.uploader.upload_large(file, **options)
        else:
            payload = cloudinary.uploader.upload(file, **options)
    except Exception as exc:  # SDK raises several unrelated error types
        # exc_info carries the SDK error, never the credentials: the SDK does not
        # put the secret in its exception text, and we log no config here.
        logger.error(
            "Cloudinary upload failed (domain=%s, resource_type=%s, bytes=%s)",
            domain,
            resource_type,
            size,
            exc_info=True,
        )
        raise CloudinaryUploadError(
            "Upload to media storage failed. Please try again."
        ) from exc

    secure_url = payload.get("secure_url") or payload.get("url")
    returned_public_id = payload.get("public_id")
    if not secure_url or not returned_public_id:
        logger.error(
            "Cloudinary upload returned no usable URL (domain=%s, keys=%s)",
            domain,
            sorted(payload.keys()),
        )
        raise CloudinaryUploadError("Media storage returned an unusable response.")

    return UploadResult(
        secure_url=secure_url,
        public_id=returned_public_id,
        resource_type=payload.get("resource_type") or resource_type,
        format=payload.get("format"),
        width=payload.get("width"),
        height=payload.get("height"),
        bytes=payload.get("bytes"),
        duration=payload.get("duration"),
    )


# ── Deletion ────────────────────────────────────────────────────────────────

_CLOUDINARY_HOSTS = {"res.cloudinary.com"}
# ".../<resource_type>/<delivery_type>/[v123/]<public id with folders>.<ext>"
_DELIVERY_RE = re.compile(
    r"^/(?P<cloud>[^/]+)/(?P<resource_type>image|video|raw)/(?P<delivery>[^/]+)/(?P<rest>.+)$"
)


def is_cloudinary_url(url: str) -> bool:
    """True when ``url`` is served by Cloudinary rather than local MEDIA_URL."""
    if not url:
        return False
    try:
        return (urlparse(url).hostname or "").lower() in _CLOUDINARY_HOSTS
    except ValueError:
        return False


def parse_cloudinary_url(url: str) -> tuple[str, str] | None:
    """
    Recover ``(public_id, resource_type)`` from a delivery URL.

    Lets media be deleted without storing a second copy of the identifier in the
    database — the URL the row already holds is enough. Returns None when the URL
    is not a recognisable Cloudinary delivery URL.
    """
    if not is_cloudinary_url(url):
        return None
    match = _DELIVERY_RE.match(urlparse(url).path)
    if not match:
        return None

    rest = match.group("rest")
    # Everything up to and including the version segment ("so_5,eo_20/v1699999999/")
    # is delivery transformation, not part of the public id.
    version = re.search(r"(?:^|/)v\d+/", rest)
    if version:
        rest = rest[version.end():]
    # `raw` keeps its extension as part of the public id; image/video do not.
    if match.group("resource_type") != "raw":
        rest = rest.rsplit(".", 1)[0]
    if not rest:
        return None
    return rest, match.group("resource_type")


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    """
    Download a stored asset's bytes.

    Needed where code has to re-read media it previously stored — the AI
    pipelines reopen an image to reprocess it, and a Cloudinary URL cannot be
    handed to ``default_storage.open``. Raises :class:`CloudinaryUploadError` so
    callers handle one error type.
    """
    import requests

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        logger.error("Could not fetch stored media (url_host=%s)", urlparse(url).hostname, exc_info=True)
        raise CloudinaryUploadError("Stored media could not be retrieved.") from exc
    return response.content


def destroy_by_url(url: str) -> bool:
    """
    Delete the asset a delivery URL points at. True when it is gone.

    Never raises: losing the remote copy must not fail the database operation
    that triggered it, so failures are logged and reported as False.
    """
    parsed = parse_cloudinary_url(url)
    if not parsed or not is_enabled():
        return False
    public_id, resource_type = parsed

    import cloudinary.uploader

    try:
        result = cloudinary.uploader.destroy(
            public_id, resource_type=resource_type, invalidate=True
        )
    except Exception:
        logger.error(
            "Cloudinary delete failed (public_id=%s, resource_type=%s)",
            public_id,
            resource_type,
            exc_info=True,
        )
        return False

    outcome = (result or {}).get("result")
    if outcome not in ("ok", "not found"):
        logger.warning(
            "Cloudinary delete returned %s (public_id=%s)", outcome, public_id
        )
        return False
    return True


# ── Trimming ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrimResult:
    """The trimmed rendition of a stored video."""

    secure_url: str
    bytes: int | None
    duration_seconds: int


def trim_video(url: str, start_seconds: float, end_seconds: float) -> TrimResult:
    """
    Cut a stored Cloudinary video to ``[start, end]`` seconds.

    Cloudinary does the cutting (start/end offsets on an eagerly generated
    rendition), so nothing is downloaded and there is no ffmpeg on the web
    server. The original asset stays untouched, like the local-disk trim; the
    row is pointed at the rendition's URL. Raises :class:`CloudinaryUploadError`.
    """
    parsed = parse_cloudinary_url(url)
    if not parsed or parsed[1] != "video":
        raise CloudinaryUploadError("This media is not a Cloudinary video.", status_code=400)
    if not is_enabled():
        raise CloudinaryUploadError("Media storage is not configured on this server.", status_code=503)
    if not end_seconds > start_seconds >= 0:
        raise CloudinaryUploadError("The trim range is not valid.", status_code=400)
    public_id, _ = parsed

    import cloudinary.uploader

    try:
        result = cloudinary.uploader.explicit(
            public_id,
            type="upload",
            resource_type="video",
            # Synchronous: the row must point at a rendition that exists by the time
            # this returns, or the post would show a broken video.
            eager=[{"start_offset": round(start_seconds, 2), "end_offset": round(end_seconds, 2)}],
            eager_async=False,
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.error("Cloudinary trim failed (public_id=%s)", public_id, exc_info=True)
        raise CloudinaryUploadError("The video could not be trimmed. Please try again.") from exc

    derived = ((result or {}).get("eager") or [None])[0] or {}
    secure_url = derived.get("secure_url") or derived.get("url")
    if not secure_url:
        logger.error("Cloudinary trim returned no rendition (public_id=%s)", public_id)
        raise CloudinaryUploadError("Media storage returned an unusable response.")
    return TrimResult(
        secure_url=secure_url,
        bytes=derived.get("bytes"),
        duration_seconds=int(round(end_seconds - start_seconds)),
    )
