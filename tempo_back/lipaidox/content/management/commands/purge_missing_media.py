"""
Find (and optionally clean up) posts whose media files no longer exist.

    python manage.py purge_missing_media                 # report only — changes nothing
    python manage.py purge_missing_media --apply         # archive them (hidden from the feed, reversible)
    python manage.py purge_missing_media --apply --delete   # hard-delete the ones with no purchases

Why this exists: before uploads moved to Cloudinary, files were written to Render's
disk, which is wiped on every restart. The database rows survived, so the feed shows
posts whose video/photo 404s. This finds them by checking every locally stored media
URL against MEDIA_ROOT.

A post counts as broken only when it has media, every one of its media files is a local
file, and ALL of them are missing. A gallery with some surviving photos, a post whose
media is on Cloudinary/elsewhere, and text posts are left alone.

Safety: dry-run is the default; archiving is reversible (status back to published);
posts that were ever bought or earned money are never hard-deleted (deleting a post
cascades to its purchase records) — with --delete they are archived instead. It also
refuses to run when MEDIA_ROOT itself is missing, since then every file looks gone.
"""
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lipaidox.content.models import Content, ContentStatus


def local_media_path(url: str) -> Path | None:
    """The file a `/media/...` URL points at under MEDIA_ROOT, or None if the URL isn't ours."""
    if not url:
        return None
    marker = settings.MEDIA_URL
    path = unquote(urlparse(url).path)
    if not path.startswith(marker):
        return None
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path[len(marker):]).resolve()
    # Never step outside MEDIA_ROOT, whatever the stored URL says.
    return target if root in target.parents else None


def has_money(content: Content) -> bool:
    from lipaidox.ppv.models import PPVPurchase

    return (
        (content.purchase_count or 0) > 0
        or (content.total_revenue or 0) > 0
        or PPVPurchase.objects.filter(content=content).exists()
    )


class Command(BaseCommand):
    help = "Report or clean up posts whose media files are gone (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually change things (default: report only).")
        parser.add_argument("--delete", action="store_true", help="With --apply: hard-delete broken posts that have no purchases.")

    def handle(self, *args, **opts):
        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            raise CommandError(
                f"MEDIA_ROOT ({root}) does not exist, so every file would look missing. "
                "Fix the storage path first — nothing was changed."
            )

        broken, partial, checked = [], [], 0
        for content in Content.objects.prefetch_related("media").iterator():
            rows = list(content.media.all())
            if not rows:
                continue
            urls = [m.file_url for m in rows] + [m.thumbnail_url for m in rows if m.thumbnail_url]
            paths = [local_media_path(u) for u in urls]
            local = [p for p in paths if p is not None]
            if not local:
                continue  # media lives elsewhere (Cloudinary, a CDN) — not ours to judge
            checked += 1
            missing = [p for p in local if not p.exists()]
            if not missing:
                continue
            main_local = [local_media_path(m.file_url) for m in rows]
            main_local = [p for p in main_local if p is not None]
            everything_local = len(local) == len(urls)
            if everything_local and main_local and all(not p.exists() for p in main_local):
                broken.append(content)
            else:
                partial.append(content)

        self.stdout.write(f"Checked {checked} post(s) with locally stored media under {root}.")
        self.stdout.write(f"  Broken (nothing viewable left): {len(broken)}")
        self.stdout.write(f"  Partly missing (left alone):     {len(partial)}")
        for c in broken:
            tag = " [has purchases]" if has_money(c) else ""
            self.stdout.write(f"    - {c.id}  {c.status:10s} {c.title[:50]!r}{tag}")
        for c in partial:
            self.stdout.write(f"    ~ {c.id}  {c.title[:50]!r}  (some files missing)")

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing changed. Re-run with --apply to act."))
            return

        archived = deleted = 0
        with transaction.atomic():
            for c in broken:
                if opts["delete"] and not has_money(c):
                    c.delete()
                    deleted += 1
                elif c.status != ContentStatus.ARCHIVED:
                    c.status = ContentStatus.ARCHIVED
                    c.save(update_fields=["status"])
                    archived += 1
        self.stdout.write(self.style.SUCCESS(f"Done: archived {archived}, deleted {deleted}."))
