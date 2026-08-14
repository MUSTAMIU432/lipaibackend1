"""
Apply video operations to a stored ContentMedia and persist the result.

Bridges `video_ops` (pure ffmpeg) and the model/storage layer: resolve the
media's file on disk, run the operation, write the new file next to it, and
update the row (file_url, size, duration). The old file is left in place — media
is content, and a failed or reverted edit should never destroy the original.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from lipaidox.content.models import ContentMedia

from . import video_ops


def _media_relpath_from_url(file_url: str) -> str:
    """
    The MEDIA_ROOT-relative path for a stored file_url.

    file_url may be absolute (`http://host/media/content/..`) or relative
    (`/media/content/..`); either way the part after MEDIA_URL is the on-disk
    path under MEDIA_ROOT.
    """
    marker = settings.MEDIA_URL  # e.g. "/media/"
    idx = file_url.find(marker)
    if idx == -1:
        raise video_ops.VideoOpError(f"file_url is not under MEDIA_URL: {file_url}")
    return file_url[idx + len(marker):].split("?", 1)[0]


def _url_for_relpath(old_url: str, new_relpath: str) -> str:
    """Rebuild a URL of the same shape as old_url but pointing at new_relpath."""
    marker = settings.MEDIA_URL
    idx = old_url.find(marker)
    origin = old_url[:idx]  # "" for a relative url, or "http://host" for absolute
    return f"{origin}{marker}{new_relpath}"


def trim_content_media(media: ContentMedia, start_seconds: float, end_seconds: float) -> ContentMedia:
    """
    Trim a video ContentMedia to [start, end] and update the row in place.

    Returns the same (refreshed) instance. Raises VideoOpError on any failure,
    leaving the original file and row untouched.
    """
    relpath = _media_relpath_from_url(media.file_url)
    src_abs = Path(settings.MEDIA_ROOT) / relpath
    new_abs = Path(video_ops.trim_file(str(src_abs), start_seconds, end_seconds))

    new_relpath = str(new_abs.relative_to(Path(settings.MEDIA_ROOT)))
    media.file_url = _url_for_relpath(media.file_url, new_relpath)
    media.file_name = new_abs.name
    media.file_size_bytes = new_abs.stat().st_size
    media.duration_seconds = int(round(video_ops.probe_duration(str(new_abs))))
    media.save(update_fields=["file_url", "file_name", "file_size_bytes", "duration_seconds"])
    return media
