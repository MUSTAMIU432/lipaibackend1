"""
Range-aware media serving for development.

Django's built-in ``static.serve`` (and ``django.views.static.serve``) return the
whole file with ``200 OK`` even for a ``Range`` request. Mobile ``<video>`` players
(Android WebView / mobile Chrome) will NOT play a video unless the server answers
``Range`` with ``206 Partial Content``. This view streams just the requested byte
range, so video seeks/buffering behave correctly on phones.
"""
import mimetypes
import os
import re

from django.db import connections
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    StreamingHttpResponse,
)

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _read_chunk(fileobj, length, block=64 * 1024):
    remaining = length
    try:
        while remaining > 0:
            data = fileobj.read(min(block, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data
    finally:
        fileobj.close()


def ranged_media_serve(request, path, document_root=None):
    root = os.path.normpath(document_root or "")
    fullpath = os.path.normpath(os.path.join(root, path))
    # Block path traversal outside the media root.
    if not fullpath.startswith(root + os.sep) and fullpath != root:
        raise Http404("Not found")
    if not os.path.isfile(fullpath):
        raise Http404("Not found")

    size = os.path.getsize(fullpath)
    content_type = mimetypes.guess_type(fullpath)[0] or "application/octet-stream"

    # Middleware (tenant lookup, sessions) opened a DB connection on this request
    # thread. A video stream can stay open for minutes (paused players, buffered
    # range requests), and each open stream otherwise pins one Postgres connection
    # — enough parallel players exhaust max_connections and 500 the whole API.
    # Nothing below touches the DB, so release the connection before streaming.
    connections.close_all()

    match = _RANGE_RE.match(request.headers.get("Range", "").strip())
    if match and size:
        start = int(match.group(1)) if match.group(1) else 0
        end = int(match.group(2)) if match.group(2) else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            resp["Accept-Ranges"] = "bytes"
            return resp
        length = end - start + 1
        fileobj = open(fullpath, "rb")
        fileobj.seek(start)
        resp = StreamingHttpResponse(
            _read_chunk(fileobj, length), status=206, content_type=content_type
        )
        resp["Content-Length"] = str(length)
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Accept-Ranges"] = "bytes"
        return resp

    # No range → stream the full file, but advertise range support.
    resp = FileResponse(open(fullpath, "rb"), content_type=content_type)
    resp["Content-Length"] = str(size)
    resp["Accept-Ranges"] = "bytes"
    return resp
