"""
Server-side video operations (ffmpeg).

The mobile/web clients cannot trim or transcode locally in any portable way, so
edits are described by the client (trim in/out, later crop/filter) and applied
here where ffmpeg is stable. This module is the thin, pure layer over the ffmpeg
binary; the Django-aware "load a ContentMedia, apply, save" logic lives in
`services.py` so this stays trivially testable.

ffmpeg is located via `settings.FFMPEG_BINARY` if set, else `ffmpeg` on PATH,
else a `~/bin/ffmpeg` fallback (a static build drop-in for hosts without a
system package). The same resolution is used for `ffprobe`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from django.conf import settings


def _resolve(binary: str, setting_name: str) -> str:
    configured = getattr(settings, setting_name, "")
    if configured:
        return configured
    found = shutil.which(binary)
    if found:
        return found
    fallback = Path.home() / "bin" / binary
    return str(fallback) if fallback.exists() else binary


def ffmpeg_bin() -> str:
    return _resolve("ffmpeg", "FFMPEG_BINARY")


def ffprobe_bin() -> str:
    return _resolve("ffprobe", "FFPROBE_BINARY")


class VideoOpError(RuntimeError):
    """A video operation failed — ffmpeg missing, unreadable input, or bad range."""


def probe_duration(path: str) -> float:
    """Duration of a media file in seconds, or 0.0 if it cannot be read."""
    try:
        out = subprocess.run(
            [ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return float((out.stdout or "0").strip() or 0.0)
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        return 0.0


def trim_file(src_path: str, start_s: float, end_s: float) -> str:
    """
    Trim `src_path` to [start_s, end_s] and return the path of the new file.

    Re-encodes rather than stream-copying: stream-copy snaps the cut to the
    nearest keyframe, so a request to trim to 2.0s can return 3.0s. A content
    edit has to be frame-accurate, and these clips are short, so the re-encode
    cost is acceptable. `-movflags +faststart` puts the moov atom first so the
    result streams (plays before fully downloaded) on mobile.
    """
    src = Path(src_path)
    if not src.is_file():
        raise VideoOpError(f"source not found: {src_path}")

    duration = probe_duration(src_path)
    start = max(0.0, float(start_s))
    end = float(end_s)
    if duration and end > duration:
        end = duration
    if end - start < 0.1:
        raise VideoOpError(f"trim range too short: {start:.2f}s..{end:.2f}s")

    out = src.with_name(f"{uuid.uuid4().hex}{src.suffix or '.mp4'}")
    cmd = [
        ffmpeg_bin(), "-y",
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
    except FileNotFoundError as exc:
        raise VideoOpError("ffmpeg not found — set FFMPEG_BINARY or install ffmpeg") from exc
    except subprocess.CalledProcessError as exc:
        raise VideoOpError(f"ffmpeg failed: {(exc.stderr or '')[-500:]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoOpError("ffmpeg timed out") from exc

    if not out.is_file() or out.stat().st_size == 0:
        raise VideoOpError("ffmpeg produced no output")
    return str(out)
