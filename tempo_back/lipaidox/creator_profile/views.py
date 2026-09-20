import logging
import mimetypes
import os
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from lipaidox.auth.jwt_auth import authenticate_request
from lipaidox.media_processor import cloudinary_service

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

ALLOWED_CONTENT_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
}
ALLOWED_CONTENT_IMAGE_TYPES = ALLOWED_IMAGE_TYPES
ALLOWED_CONTENT_PDF_TYPES = {"application/pdf"}
ALLOWED_CONTENT_ARCHIVE_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/vnd.rar",
}
# Voice notes (DM + live). expo-audio records AAC-in-MP4 (.m4a); the various
# platforms/label it differently, so accept the common audio content types.
ALLOWED_CONTENT_AUDIO_TYPES = {
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/aac",
    "audio/mpeg",
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
}

# Per-type upload limits for creator content (REST body; tune via reverse proxy too).
_MAX_CONTENT_IMAGE = 30 * 1024 * 1024
_MAX_CONTENT_VIDEO = 500 * 1024 * 1024
_MAX_CONTENT_PDF = 80 * 1024 * 1024
_MAX_CONTENT_ARCHIVE = 500 * 1024 * 1024
_MAX_CONTENT_AUDIO = 30 * 1024 * 1024


def _store_locally(file, *, domain: str, user_id, filename: str) -> str:
    """
    Write the upload under MEDIA_ROOT and return its MEDIA_URL path.

    The pre-Cloudinary behaviour, kept for local development and for any
    environment without Cloudinary credentials. On Render this storage is
    ephemeral — see the MEDIA_ROOT note in settings.
    """
    upload_dir = os.path.join(settings.MEDIA_ROOT, domain, str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb+") as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    return f"{settings.MEDIA_URL}{domain}/{user_id}/{filename}"


def _store_upload(file, *, domain: str, user_id, content_type: str, filename: str) -> str:
    """
    Persist an upload and return the URL to store in the database.

    Cloudinary when it is configured (an absolute HTTPS URL that survives a
    Render restart), otherwise the local MEDIA_ROOT path. Raises
    ``CloudinaryUploadError`` when a configured Cloudinary upload fails, so the
    caller can answer with a meaningful status instead of a bare 500.
    """
    if cloudinary_service.is_enabled():
        result = cloudinary_service.upload_file(
            file, domain=domain, user_id=user_id, content_type=content_type
        )
        return result.secure_url
    return _store_locally(file, domain=domain, user_id=user_id, filename=filename)


def _get_user(request):
    """Authenticate via Bearer token and return the User, or None."""
    authenticate_request(request)
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return user
    return None


@csrf_exempt
def upload_profile_photo(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user = _get_user(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    photo_type = request.POST.get("type", "profile")
    if photo_type not in ("profile", "cover"):
        return JsonResponse({"error": "type must be 'profile' or 'cover'"}, status=400)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse(
            {"error": f"Invalid file type. Allowed: JPEG, PNG, WebP, GIF"},
            status=400,
        )

    if file.size > MAX_FILE_SIZE:
        return JsonResponse({"error": "File too large. Maximum 5 MB."}, status=400)

    ext = os.path.splitext(file.name)[1].lower() or ".jpg"
    filename = f"{photo_type}_{user.id}_{uuid.uuid4().hex[:8]}{ext}"

    try:
        url = _store_upload(
            file,
            domain="profiles",
            user_id=user.id,
            content_type=file.content_type,
            filename=filename,
        )
    except cloudinary_service.CloudinaryUploadError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status_code)

    try:
        profile = user.profile
        if photo_type == "profile":
            profile.profile_photo_url = url
        else:
            profile.cover_photo_url = url
        profile.save(update_fields=[f"{photo_type}_photo_url" if photo_type == "cover" else "profile_photo_url"])
    except Exception:
        # The photo is stored but no row points at it. Drop the remote copy so a
        # retry does not accumulate orphaned assets; the local-disk branch keeps
        # its previous best-effort behaviour of leaving the file in place.
        logger.error(
            "Profile photo saved to storage but profile update failed (user=%s)",
            user.id,
            exc_info=True,
        )
        cloudinary_service.destroy_by_url(url)
        return JsonResponse({"error": "Could not save the photo to your profile."}, status=500)

    return JsonResponse({"url": url, "type": photo_type})


def _content_upload_max_bytes(content_type: str) -> int:
    if content_type.startswith("video/"):
        return _MAX_CONTENT_VIDEO
    if content_type.startswith("image/"):
        return _MAX_CONTENT_IMAGE
    if content_type.startswith("audio/"):
        return _MAX_CONTENT_AUDIO
    if content_type in ALLOWED_CONTENT_PDF_TYPES:
        return _MAX_CONTENT_PDF
    if content_type in ALLOWED_CONTENT_ARCHIVE_TYPES:
        return _MAX_CONTENT_ARCHIVE
    return 50 * 1024 * 1024


def _content_upload_allowed_type(content_type: str) -> bool:
    if content_type in ALLOWED_CONTENT_IMAGE_TYPES:
        return True
    if content_type in ALLOWED_CONTENT_VIDEO_TYPES:
        return True
    if content_type in ALLOWED_CONTENT_AUDIO_TYPES:
        return True
    if content_type in ALLOWED_CONTENT_PDF_TYPES:
        return True
    if content_type in ALLOWED_CONTENT_ARCHIVE_TYPES:
        return True
    return False


@csrf_exempt
def upload_content_media(request):
    """
    Store binary for GraphQL `fileUrl` fields (main media, thumbnails, attachments, slides).

    Returns `{"url": ...}` — an absolute Cloudinary HTTPS URL when Cloudinary is
    configured, otherwise a local MEDIA_URL path. Either way it is a durable URL
    the client stores on the GraphQL record, never a browser `blob:` URL.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user = _get_user(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    # No creator gate: any authenticated user uploads media here, because DM
    # attachments — photos and voice notes — are sent by fans too, not only
    # creators publishing content. Uploads stay type- and size-limited and are
    # namespaced under the uploader's id below.

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    ct = (file.content_type or "").strip().lower()
    if not ct:
        guessed, _ = mimetypes.guess_type(file.name)
        ct = (guessed or "").lower()
    if not _content_upload_allowed_type(ct):
        return JsonResponse(
            {"error": f"Unsupported file type: {ct or 'unknown'}"},
            status=400,
        )

    max_bytes = _content_upload_max_bytes(ct)
    if file.size > max_bytes:
        return JsonResponse(
            {"error": f"File too large for this type (max {max_bytes // (1024 * 1024)} MB)."},
            status=400,
        )

    ext = os.path.splitext(file.name)[1].lower()
    if not ext:
        if ct.startswith("video/"):
            ext = ".mp4"
        elif ct.startswith("image/"):
            ext = ".jpg"
        elif ct.startswith("audio/"):
            ext = ".m4a"
        elif ct in ALLOWED_CONTENT_PDF_TYPES:
            ext = ".pdf"
        elif ct in ALLOWED_CONTENT_ARCHIVE_TYPES:
            ext = ".zip"
        else:
            ext = ".bin"

    filename = f"{uuid.uuid4().hex}{ext}"

    try:
        url = _store_upload(
            file,
            domain="content",
            user_id=user.id,
            content_type=ct,
            filename=filename,
        )
    except cloudinary_service.CloudinaryUploadError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status_code)
    except OSError:
        # Local-disk branch: a full or read-only volume must not surface as an
        # unexplained 500 the app cannot act on.
        logger.error("Local media write failed (user=%s)", user.id, exc_info=True)
        return JsonResponse({"error": "Could not store the uploaded file."}, status=507)

    return JsonResponse({"url": url})
