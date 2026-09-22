"""
Tests for the Cloudinary media upload service.

Cloudinary itself is always mocked: these must never touch the real account, and
they must pass with no credentials configured (as in CI).
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from lipaidox.media_processor import cloudinary_service as svc


CLOUDINARY_ON = dict(
    CLOUDINARY_ENABLED=True,
    CLOUDINARY_CLOUD_NAME="test-cloud",
    CLOUDINARY_FOLDER="lipaidox",
)


class ResourceTypeTests(SimpleTestCase):
    """A video must never be uploaded as an image."""

    def test_images_map_to_image(self):
        for ct in ("image/jpeg", "image/png", "image/webp", "IMAGE/GIF"):
            self.assertEqual(svc.resource_type_for(ct), "image")

    def test_videos_map_to_video(self):
        for ct in ("video/mp4", "video/quicktime", "video/webm"):
            self.assertEqual(svc.resource_type_for(ct), "video")

    def test_documents_and_audio_map_to_raw(self):
        for ct in ("application/pdf", "application/zip", "audio/m4a", ""):
            self.assertEqual(svc.resource_type_for(ct), "raw")


class UploadTests(SimpleTestCase):
    def _file(self, size=1024, name="clip.mp4"):
        f = MagicMock()
        f.size = size
        f.name = name
        return f

    @override_settings(**CLOUDINARY_ON)
    def test_image_upload_returns_secure_url_and_metadata(self):
        payload = {
            "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/v1/lipaidox/content/7/abc.jpg",
            "public_id": "lipaidox/content/7/abc",
            "resource_type": "image",
            "format": "jpg",
            "width": 800,
            "height": 600,
            "bytes": 2048,
        }
        with patch("cloudinary.uploader.upload", return_value=payload) as up:
            result = svc.upload_file(
                self._file(name="a.jpg"), domain="content", user_id=7, content_type="image/jpeg"
            )

        self.assertEqual(result.secure_url, payload["secure_url"])
        self.assertEqual(result.public_id, payload["public_id"])
        self.assertEqual(result.resource_type, "image")
        self.assertEqual((result.width, result.height), (800, 600))
        # Folder mirrors the local <domain>/<user id> layout it replaces.
        self.assertEqual(up.call_args.kwargs["folder"], "lipaidox/content/7")
        self.assertEqual(up.call_args.kwargs["resource_type"], "image")

    @override_settings(**CLOUDINARY_ON)
    def test_video_upload_uses_video_resource_type(self):
        payload = {
            "secure_url": "https://res.cloudinary.com/test-cloud/video/upload/v1/lipaidox/content/7/v.mp4",
            "public_id": "lipaidox/content/7/v",
            "resource_type": "video",
            "duration": 12.5,
        }
        with patch("cloudinary.uploader.upload", return_value=payload) as up:
            result = svc.upload_file(
                self._file(), domain="content", user_id=7, content_type="video/mp4"
            )

        self.assertEqual(up.call_args.kwargs["resource_type"], "video")
        self.assertEqual(result.duration, 12.5)

    @override_settings(**CLOUDINARY_ON)
    def test_large_video_uses_chunked_upload(self):
        big = self._file(size=svc.LARGE_UPLOAD_THRESHOLD_BYTES + 1)
        payload = {
            "secure_url": "https://res.cloudinary.com/test-cloud/video/upload/v1/big.mp4",
            "public_id": "big",
            "resource_type": "video",
        }
        with patch("cloudinary.uploader.upload_large", return_value=payload) as large, patch(
            "cloudinary.uploader.upload"
        ) as normal:
            svc.upload_file(big, domain="content", user_id=1, content_type="video/mp4")

        large.assert_called_once()
        normal.assert_not_called()

    @override_settings(**CLOUDINARY_ON)
    def test_sdk_failure_becomes_application_error(self):
        with patch("cloudinary.uploader.upload", side_effect=RuntimeError("boom")):
            with self.assertRaises(svc.CloudinaryUploadError) as ctx:
                svc.upload_file(
                    self._file(), domain="content", user_id=1, content_type="image/png"
                )

        self.assertEqual(ctx.exception.status_code, 502)
        # The client-facing message must not leak the underlying error.
        self.assertNotIn("boom", str(ctx.exception))

    @override_settings(**CLOUDINARY_ON)
    def test_response_without_url_is_rejected(self):
        with patch("cloudinary.uploader.upload", return_value={"public_id": "x"}):
            with self.assertRaises(svc.CloudinaryUploadError):
                svc.upload_file(
                    self._file(), domain="content", user_id=1, content_type="image/png"
                )

    @override_settings(CLOUDINARY_ENABLED=False)
    def test_upload_without_credentials_raises_service_unavailable(self):
        with self.assertRaises(svc.CloudinaryUploadError) as ctx:
            svc.upload_file(self._file(), domain="content", user_id=1, content_type="image/png")
        self.assertEqual(ctx.exception.status_code, 503)


class PrivateUploadTests(SimpleTestCase):
    """Identity documents must not be world-readable."""

    def _file(self):
        f = MagicMock()
        f.size = 1024
        f.name = "id.jpg"
        return f

    @override_settings(**CLOUDINARY_ON)
    def test_private_upload_requests_authenticated_type(self):
        payload = {
            "secure_url": "https://res.cloudinary.com/test-cloud/image/authenticated/v1/id.jpg",
            "public_id": "id",
            "resource_type": "image",
        }
        with patch("cloudinary.uploader.upload", return_value=payload) as up:
            svc.upload_file(
                self._file(), domain="kyc", user_id=3, content_type="image/jpeg", private=True
            )
        self.assertEqual(up.call_args.kwargs["type"], "authenticated")

    @override_settings(**CLOUDINARY_ON)
    def test_ordinary_upload_is_not_authenticated(self):
        payload = {
            "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/v1/a.jpg",
            "public_id": "a",
            "resource_type": "image",
        }
        with patch("cloudinary.uploader.upload", return_value=payload) as up:
            svc.upload_file(
                self._file(), domain="content", user_id=3, content_type="image/jpeg"
            )
        self.assertNotIn("type", up.call_args.kwargs)


class FetchBytesTests(SimpleTestCase):
    """Reprocessing must be able to reopen an image stored on Cloudinary."""

    def test_fetch_returns_body(self):
        response = MagicMock()
        response.content = b"jpegbytes"
        response.raise_for_status.return_value = None
        with patch("requests.get", return_value=response):
            self.assertEqual(svc.fetch_bytes("https://res.cloudinary.com/d/image/upload/a.jpg"), b"jpegbytes")

    def test_fetch_failure_raises_application_error(self):
        with patch("requests.get", side_effect=RuntimeError("dns")):
            with self.assertRaises(svc.CloudinaryUploadError):
                svc.fetch_bytes("https://res.cloudinary.com/d/image/upload/a.jpg")


class UrlParsingTests(SimpleTestCase):
    """public_id is recovered from the stored URL, so no extra column is needed."""

    def test_image_url(self):
        url = "https://res.cloudinary.com/demo/image/upload/v1699999999/lipaidox/content/7/abc.jpg"
        self.assertEqual(svc.parse_cloudinary_url(url), ("lipaidox/content/7/abc", "image"))

    def test_video_url_without_version(self):
        url = "https://res.cloudinary.com/demo/video/upload/lipaidox/content/7/clip.mp4"
        self.assertEqual(svc.parse_cloudinary_url(url), ("lipaidox/content/7/clip", "video"))

    def test_raw_url_keeps_extension(self):
        url = "https://res.cloudinary.com/demo/raw/upload/v1/lipaidox/content/7/notes.pdf"
        self.assertEqual(svc.parse_cloudinary_url(url), ("lipaidox/content/7/notes.pdf", "raw"))

    def test_legacy_local_media_url_is_not_cloudinary(self):
        self.assertIsNone(svc.parse_cloudinary_url("/media/content/7/abc.jpg"))
        self.assertIsNone(
            svc.parse_cloudinary_url("https://lipaibackend1.onrender.com/media/content/7/a.jpg")
        )
        self.assertFalse(svc.is_cloudinary_url(""))


class DestroyTests(SimpleTestCase):
    @override_settings(**CLOUDINARY_ON)
    def test_destroy_calls_sdk_with_public_id_and_type(self):
        url = "https://res.cloudinary.com/demo/video/upload/v1/lipaidox/content/7/clip.mp4"
        with patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as destroy:
            self.assertTrue(svc.destroy_by_url(url))

        self.assertEqual(destroy.call_args.args[0], "lipaidox/content/7/clip")
        self.assertEqual(destroy.call_args.kwargs["resource_type"], "video")

    @override_settings(**CLOUDINARY_ON)
    def test_destroy_never_raises_on_sdk_failure(self):
        url = "https://res.cloudinary.com/demo/image/upload/v1/a.jpg"
        with patch("cloudinary.uploader.destroy", side_effect=RuntimeError("nope")):
            self.assertFalse(svc.destroy_by_url(url))

    @override_settings(**CLOUDINARY_ON)
    def test_legacy_local_url_is_ignored(self):
        """Deleting a pre-Cloudinary row must not call Cloudinary at all."""
        with patch("cloudinary.uploader.destroy") as destroy:
            self.assertFalse(svc.destroy_by_url("/media/content/7/old.jpg"))
        destroy.assert_not_called()


class TrimTests(SimpleTestCase):
    URL = "https://res.cloudinary.com/test-cloud/video/upload/v1/lipaidox/content/7/clip.mp4"

    def test_transformation_segments_are_not_part_of_the_public_id(self):
        derived = "https://res.cloudinary.com/test-cloud/video/upload/eo_20.0,so_5.0/v1/lipaidox/content/7/clip.mp4"
        self.assertEqual(svc.parse_cloudinary_url(derived), ("lipaidox/content/7/clip", "video"))

    @override_settings(**CLOUDINARY_ON)
    def test_trim_asks_cloudinary_for_the_range_and_returns_the_rendition(self):
        payload = {"eager": [{"secure_url": "https://res.cloudinary.com/test-cloud/video/upload/eo_20.0,so_5.0/v1/lipaidox/content/7/clip.mp4", "bytes": 4242}]}
        with patch("cloudinary.uploader.explicit", return_value=payload) as ex:
            out = svc.trim_video(self.URL, 5, 20)
        args, kwargs = ex.call_args
        self.assertEqual(args[0], "lipaidox/content/7/clip")
        self.assertEqual(kwargs["resource_type"], "video")
        self.assertEqual(kwargs["eager"], [{"start_offset": 5, "end_offset": 20}])
        self.assertFalse(kwargs["eager_async"])
        self.assertEqual((out.bytes, out.duration_seconds), (4242, 15))
        self.assertIn("so_5.0", out.secure_url)

    @override_settings(**CLOUDINARY_ON)
    def test_trim_rejects_bad_ranges_and_non_video(self):
        with patch("cloudinary.uploader.explicit") as ex:
            with self.assertRaises(svc.CloudinaryUploadError):
                svc.trim_video(self.URL, 20, 5)
            with self.assertRaises(svc.CloudinaryUploadError):
                svc.trim_video("https://res.cloudinary.com/test-cloud/image/upload/v1/a/b.jpg", 1, 2)
            ex.assert_not_called()

    @override_settings(**CLOUDINARY_ON)
    def test_trim_failure_becomes_application_error(self):
        with patch("cloudinary.uploader.explicit", side_effect=RuntimeError("boom")):
            with self.assertRaises(svc.CloudinaryUploadError):
                svc.trim_video(self.URL, 1, 5)
