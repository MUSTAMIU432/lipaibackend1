"""Tests for the `purge_missing_media` clean-up command (needs the real schema)."""
import tempfile
from decimal import Decimal as D
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from lipaidox.auth.models import User
from lipaidox.content.models import Content, ContentMedia, ContentStatus
from lipaidox.creator_profile.models import CreatorProfile


class PurgeMissingMediaTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        user = User.objects.create_user(username="c1", email="c1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=user, username="c1")

    def post(self, title, urls, **kw):
        c = Content.objects.create(creator=self.profile, title=title, status=ContentStatus.PUBLISHED, **kw)
        for i, u in enumerate(urls):
            ContentMedia.objects.create(content=c, media_type="video" if u.endswith(".mp4") else "image", file_url=u, sort_order=i)
        return c

    def keep(self, rel):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")

    def run_cmd(self, *args):
        out = StringIO()
        with override_settings(MEDIA_ROOT=self.root):
            call_command("purge_missing_media", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_but_changes_nothing(self):
        gone = self.post("gone", ["https://x.onrender.com/media/content/1/a.mp4"])
        out = self.run_cmd()
        self.assertIn("Broken (nothing viewable left): 1", out)
        self.assertIn("Dry run", out)
        gone.refresh_from_db()
        self.assertEqual(gone.status, ContentStatus.PUBLISHED)

    def test_only_fully_missing_local_posts_are_broken(self):
        self.keep("content/1/ok.jpg")
        gone = self.post("gone", ["/media/content/1/a.mp4"])
        fine = self.post("fine", ["/media/content/1/ok.jpg"])
        partial = self.post("partial", ["/media/content/1/ok.jpg", "/media/content/1/b.jpg"])
        cloud = self.post("cloud", ["https://res.cloudinary.com/c/video/upload/v1/a/b.mp4"])
        text = self.post("text", [])
        out = self.run_cmd("--apply")
        for c in (gone, fine, partial, cloud, text):
            c.refresh_from_db()
        self.assertEqual(gone.status, ContentStatus.ARCHIVED)
        for c in (fine, partial, cloud, text):
            self.assertEqual(c.status, ContentStatus.PUBLISHED, c.title)
        self.assertIn("archived 1, deleted 0", out)

    def test_delete_removes_unpurchased_but_only_archives_purchased(self):
        plain = self.post("plain", ["/media/content/1/a.mp4"])
        paid = self.post("paid", ["/media/content/1/b.mp4"], purchase_count=2, total_revenue=D("9.00"))
        out = self.run_cmd("--apply", "--delete")
        self.assertFalse(Content.objects.filter(pk=plain.pk).exists())
        paid.refresh_from_db()
        self.assertEqual(paid.status, ContentStatus.ARCHIVED)
        self.assertIn("archived 1, deleted 1", out)

    def test_refuses_when_media_root_is_missing(self):
        self.post("gone", ["/media/content/1/a.mp4"])
        with override_settings(MEDIA_ROOT=self.root / "nope"):
            with self.assertRaises(CommandError):
                call_command("purge_missing_media", "--apply", stdout=StringIO())
        self.assertEqual(Content.objects.filter(status=ContentStatus.ARCHIVED).count(), 0)


# ═════════════════════════════════════════════════════════════════════════════
# Engagement — likes, saves and shares persist and come back on the next read
# ═════════════════════════════════════════════════════════════════════════════

from types import SimpleNamespace as NS  # noqa: E402

from lipaidox_backend.schema import schema  # noqa: E402


def gql(user, query, variables=None):
    """Run a document through the real schema as `user`; returns (data, errors)."""
    request = NS(user=user, META={"REMOTE_ADDR": "10.0.0.7", "HTTP_USER_AGENT": "tests"})
    result = schema.execute_sync(query, variable_values=variables or {}, context_value=NS(request=request))
    return result.data, [str(e) for e in (result.errors or [])]


READ = """query($id: ID!) { contentById(id: $id) { likeCount shareCount isLikedByViewer isSavedByViewer } }"""


class EngagementTests(TestCase):
    def setUp(self):
        creator = User.objects.create_user(username="c1", email="c1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=creator, username="c1")
        self.fan = User.objects.create_user(username="f1", email="f1@example.com", password="x", role="fan")
        self.content = Content.objects.create(creator=self.profile, title="p", status=ContentStatus.PUBLISHED)
        self.vars = {"id": str(self.content.id)}

    def read(self):
        data, errors = gql(self.fan, READ, self.vars)
        self.assertEqual(errors, [])
        return data["contentById"]

    def test_like_and_save_survive_a_fresh_read(self):
        gql(self.fan, "mutation($id: ID!) { likeContent(contentId: $id) { liked } }", self.vars)
        gql(self.fan, "mutation($id: ID!) { saveContent(contentId: $id) { saved } }", self.vars)
        row = self.read()
        self.assertEqual(row["likeCount"], 1)
        self.assertTrue(row["isLikedByViewer"])
        self.assertTrue(row["isSavedByViewer"])

        gql(self.fan, "mutation($id: ID!) { unlikeContent(contentId: $id) { liked } }", self.vars)
        row = self.read()
        self.assertEqual(row["likeCount"], 0)
        self.assertFalse(row["isLikedByViewer"])

    def test_share_is_counted_and_returned(self):
        doc = "mutation($id: ID!) { recordContentShare(contentId: $id) { shareCount } }"
        data, errors = gql(self.fan, doc, self.vars)
        self.assertEqual(errors, [])
        self.assertEqual(data["recordContentShare"]["shareCount"], 1)
        gql(self.fan, doc, self.vars)
        self.assertEqual(self.read()["shareCount"], 2)

    def test_hidden_counts_are_withheld_from_others(self):
        self.content.hide_engagement_counts = True
        self.content.share_count = 5
        self.content.save()
        self.assertEqual(self.read()["shareCount"], 0)
