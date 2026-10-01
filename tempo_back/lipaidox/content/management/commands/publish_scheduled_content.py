"""Publish scheduled posts whose time has passed (also runs lazily and from Celery beat)."""
from django.core.management.base import BaseCommand

from lipaidox.content.scheduling import publish_due_scheduled


class Command(BaseCommand):
    help = "Publish scheduled posts whose scheduled time has passed."

    def handle(self, *args, **options):
        n = publish_due_scheduled(throttle=False)
        self.stdout.write(f"Published {n} scheduled post(s).")
