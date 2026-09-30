"""Public home + legal pages (DB-free: `./test.sh quick`)."""
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from lipaidox_backend import legal_pages


class LegalPagesTests(SimpleTestCase):
    def setUp(self):
        legal_pages._read.cache_clear()
        self.rf = RequestFactory()

    def get(self, path):
        match = resolve(path)
        return match.func(self.rf.get(path), **match.kwargs)

    def test_consent_screen_urls_serve_html(self):
        for path, marker in [
            ("/", "Create. Monetize. Own Your Audience."),
            ("/privacy/", "Lipaiddox Data Privacy Policy"),
            ("/terms/", "Lipaiddox Terms of Use"),
            ("/legal/cookies/", "Cookies Policy"),
        ]:
            res = self.get(path)
            self.assertEqual(res.status_code, 200, path)
            self.assertIn("text/html", res["Content-Type"])
            self.assertIn(marker, res.content.decode(), path)

    def test_unknown_document_is_404(self):
        with self.assertRaises(Http404):
            self.get("/legal/not-a-doc/")

    @override_settings(GOOGLE_SITE_VERIFICATION="abc123")
    def test_verification_meta_tag_when_configured(self):
        html = self.get("/").content.decode()
        self.assertIn('<meta name="google-site-verification" content="abc123">', html)

    def test_no_placeholder_leaks_without_token(self):
        self.assertNotIn("{{GOOGLE_SITE_VERIFICATION}}", self.get("/terms/").content.decode())
