"""
Redis/cache service, Celery wiring and /health/ — no database, no Redis needed.

    USE_SQLITE=True ./myenv/bin/python manage.py test lipaidox.tests_infrastructure

Caches are overridden to an in-memory backend so the suite never depends on
(or writes to) a developer's real Redis.
"""
import json
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from lipaidox import cache as cache_service
from lipaidox import tasking

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "infra-tests"}}


@override_settings(CACHES=LOCMEM)
class CacheServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_cache_aside_calls_loader_only_on_miss(self):
        loader = mock.Mock(return_value={"n": 1})
        first = cache_service.get_or_set("t", "a", ttl=60, loader=loader)
        second = cache_service.get_or_set("t", "a", ttl=60, loader=loader)
        self.assertEqual(first, {"n": 1})
        self.assertEqual(second, {"n": 1})
        loader.assert_called_once()

    def test_entries_expire_after_ttl(self):
        loader = mock.Mock(side_effect=[1, 2])
        with mock.patch("time.time", return_value=1_000_000.0):
            self.assertEqual(cache_service.get_or_set("t", "exp", ttl=5, loader=loader), 1)
        with mock.patch("time.time", return_value=1_000_010.0):
            self.assertEqual(cache_service.get_or_set("t", "exp", ttl=5, loader=loader), 2)

    def test_delete_cached_forces_reload(self):
        loader = mock.Mock(side_effect=["old", "new"])
        cache_service.get_or_set("t", 7, ttl=60, loader=loader)
        cache_service.delete_cached("t", 7)
        self.assertEqual(cache_service.get_or_set("t", 7, ttl=60, loader=loader), "new")

    def test_invalidate_namespace_orphans_every_key(self):
        cache_service.set_cached("ns", "a", value=1, ttl=60)
        cache_service.set_cached("ns", "b", value=2, ttl=60)
        cache_service.set_cached("other", "a", value=3, ttl=60)
        cache_service.invalidate_namespace("ns")
        self.assertIsNone(cache_service.get_cached("ns", "a"))
        self.assertIsNone(cache_service.get_cached("ns", "b"))
        self.assertEqual(cache_service.get_cached("other", "a"), 3)

    def test_invalidate_namespace_survives_evicted_version_key(self):
        cache_service.set_cached("ns", "a", value=1, ttl=60)
        cache.delete("ns:version")
        cache_service.invalidate_namespace("ns")
        self.assertIsNone(cache_service.get_cached("ns", "a"))

    def test_keys_are_namespaced_and_versioned(self):
        self.assertEqual(cache_service.make_key("catalog:x", "list", None, True), "catalog:x:v1:list:-:True")

    def test_model_rows_round_trip_with_types(self):
        from lipaidox.credits.models import CreditPackage

        pk = uuid.uuid4()
        created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt_timezone.utc)
        row = CreditPackage(
            id=pk, name="Starter", credit_type="creator_credit", credit_amount=100,
            price_usd=Decimal("10.50"), created_at=created,
        )
        loader = mock.Mock(return_value=[row])
        cache_service.get_or_set_models("t", "pk", ttl=60, loader=loader)
        [hit] = cache_service.get_or_set_models("t", "pk", ttl=60, loader=loader)
        loader.assert_called_once()
        self.assertEqual(hit.pk, pk)
        self.assertEqual(hit.price_usd, Decimal("10.50"))
        self.assertEqual(hit.created_at, created)

    def test_cached_models_are_stored_as_json_not_pickle(self):
        from lipaidox.credits.models import CreditPackage

        row = CreditPackage(id=uuid.uuid4(), name="S", credit_type="creator_credit", credit_amount=1, price_usd=Decimal("1"))
        cache_service.get_or_set_models("t", "json", ttl=60, loader=lambda: [row])
        raw = cache.get(cache_service.make_key("t", "json"))
        self.assertIsInstance(raw, str)
        self.assertEqual(json.loads(raw)[0]["fields"]["name"], "S")

    def test_undecodable_entry_is_treated_as_miss(self):
        cache.set(cache_service.make_key("t", "bad"), "not json", 60)
        with self.assertLogs("lipaidox.cache", level="WARNING"):
            self.assertEqual(cache_service.get_or_set_models("t", "bad", ttl=60, loader=lambda: []), [])

    def test_cache_health_ok(self):
        self.assertIsNone(cache_service.cache_health())


class RedisUnavailableTests(SimpleTestCase):
    """With Redis down, reads fall through to the loader instead of erroring."""

    @override_settings(CACHES={"default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:1/0",  # nothing listens on port 1
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            "IGNORE_EXCEPTIONS": True,
            "SOCKET_CONNECT_TIMEOUT": 0.2,
            "SOCKET_TIMEOUT": 0.2,
        },
    }})
    def test_loader_result_served_when_redis_down(self):
        value = cache_service.get_or_set("t", "down", ttl=60, loader=lambda: {"ok": True})
        cache_service.invalidate_namespace("t")  # must not raise either
        self.assertEqual(value, {"ok": True})


class CeleryWiringTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from lipaidox_backend.celery import app

        cls.app = app
        app.loader.import_default_modules()  # runs autodiscovery like a worker does

    def test_project_tasks_are_registered(self):
        for name in (
            "lipaidox.ping",
            "lipaidox.notifications.notify_new_content_posted",
            "lipaidox.credits.bill_live_sessions",
            "lipaidox.media_processor.process_media_pipeline_task",
        ):
            self.assertIn(name, self.app.tasks)

    def test_beat_schedule_points_at_registered_tasks(self):
        for entry in self.app.conf.beat_schedule.values():
            self.assertIn(entry["task"], self.app.tasks)

    def test_json_only_serialization(self):
        self.assertEqual(self.app.conf.accept_content, ["json"])
        self.assertEqual(self.app.conf.task_serializer, "json")
        self.assertEqual(self.app.conf.result_serializer, "json")

    def test_ping_executes_and_returns_result(self):
        from lipaidox.tasks import ping

        self.assertEqual(ping.apply().get(), "pong")

    def test_task_failure_is_captured_not_raised(self):
        from lipaidox.notifications.tasks import notify_new_content_posted_task

        with mock.patch("lipaidox.content.models.Content.objects") as objects:
            objects.select_related.side_effect = RuntimeError("db down")
            result = notify_new_content_posted_task.apply(args=["x"])
        self.assertTrue(result.failed())
        self.assertIsInstance(result.result, RuntimeError)


class TaskingTests(SimpleTestCase):
    def test_enqueue_publishes_to_broker(self):
        task = mock.Mock(name="task")
        tasking.enqueue(task, "a", b=1)
        task.apply_async.assert_called_once_with(args=("a",), kwargs={"b": 1})
        task.apply.assert_not_called()

    def test_enqueue_runs_inline_when_broker_unreachable(self):
        task = mock.Mock(name="task")
        task.apply_async.side_effect = ConnectionError("broker down")
        with self.assertLogs("lipaidox.tasking", level="WARNING"):
            tasking.enqueue(task, "a")
        task.apply.assert_called_once_with(args=("a",), kwargs={})


@override_settings(CACHES=LOCMEM, CELERY_BROKER_URL="", REDIS_URL="")
class HealthViewTests(SimpleTestCase):
    def call(self):
        from lipaidox_backend.health import health_view

        return health_view(RequestFactory().get("/health/"))

    def test_reports_ok_without_leaking_config(self):
        with mock.patch("lipaidox_backend.health._database", return_value="ok"):
            resp = self.call()
        body = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("redis://", resp.content.decode())

    def test_database_down_is_503(self):
        with mock.patch("lipaidox_backend.health._database", return_value="OperationalError"):
            resp = self.call()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(json.loads(resp.content)["status"], "down")

    def test_cache_down_is_degraded_not_down(self):
        with mock.patch("lipaidox_backend.health._database", return_value="ok"), \
                mock.patch("lipaidox_backend.health.cache_health", return_value="ConnectionError"):
            resp = self.call()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["status"], "degraded")

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="web.apps.googleusercontent.com",
        GOOGLE_OAUTH_ANDROID_CLIENT_ID="android.apps.googleusercontent.com",
        GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS="",
        EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
        EMAIL_HOST_PASSWORD="smtp-secret",
        RESEND_API_KEY="re_secret",
        DEFAULT_FROM_EMAIL="Lipaidox <no-reply@lipaidox.app>",
    )
    def test_reports_auth_config_without_secrets(self):
        with mock.patch("lipaidox_backend.health._database", return_value="ok"):
            resp = self.call()
        auth = json.loads(resp.content)["auth"]
        self.assertEqual(
            auth["googleClientIds"],
            ["web.apps.googleusercontent.com", "android.apps.googleusercontent.com"],
        )
        self.assertEqual(auth["emailBackend"], "resend")
        self.assertEqual(auth["emailFromDomain"], "lipaidox.app")
        self.assertIn("emailSmtpLoginConfigured", auth)
        self.assertNotIn("no-reply", resp.content.decode())
        self.assertNotIn("secret", resp.content.decode())


class GoogleAudienceTests(SimpleTestCase):
    def audiences(self):
        from lipaidox.auth.googleOuth.googleOuth import _google_oauth_audiences

        return _google_oauth_audiences()

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="web",
        GOOGLE_OAUTH_ANDROID_CLIENT_ID="android",
        GOOGLE_OAUTH_ADDITIONAL_CLIENT_IDS="extra, web ,",
    )
    def test_web_android_and_extra_clients_are_accepted_once_each(self):
        self.assertEqual(self.audiences(), ["web", "android", "extra"])

    def test_current_and_legacy_app_web_clients_are_accepted(self):
        # The app's native sign-in mints tokens for its Web client — without it
        # every mobile Google sign-in fails "not configured". The legacy one keeps
        # APKs built before the switch working.
        audiences = self.audiences()
        self.assertTrue(any(a.startswith("289138513882-kgivgr67") for a in audiences))
        self.assertTrue(any(a.startswith("273053369879-5jdgrvn3") for a in audiences))


class EmailBackendSelectionTests(SimpleTestCase):
    """Settings pick the backend at import, so each case runs in a fresh interpreter."""

    def backend_for(self, **env):
        import os
        import subprocess
        import sys

        full = {**os.environ, "EMAIL_BACKEND": "", "EMAIL_HOST": "", **env}
        out = subprocess.run(
            [sys.executable, "-c", "from lipaidox_backend import settings as s; print(s.EMAIL_BACKEND)"],
            env=full, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip().splitlines()[-1]

    def test_gmail_sender_with_smtp_uses_smtp_not_resend(self):
        backend = self.backend_for(
            RESEND_API_KEY="re_x", EMAIL_HOST="smtp.gmail.com", DEFAULT_FROM_EMAIL="Lipaidox <me@gmail.com>",
        )
        self.assertEqual(backend, "django.core.mail.backends.smtp.EmailBackend")

    def test_own_domain_sender_keeps_resend(self):
        backend = self.backend_for(
            RESEND_API_KEY="re_x", EMAIL_HOST="smtp.gmail.com", DEFAULT_FROM_EMAIL="no-reply@lipaidox.app",
        )
        self.assertEqual(backend, "anymail.backends.resend.EmailBackend")

    def test_resend_kept_when_no_smtp_to_fall_back_to(self):
        backend = self.backend_for(RESEND_API_KEY="re_x", DEFAULT_FROM_EMAIL="me@gmail.com")
        self.assertEqual(backend, "anymail.backends.resend.EmailBackend")


class BackgroundEagerTaskTests(SimpleTestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, BACKGROUND_EAGER_TASKS=True)
    def test_eager_task_runs_on_a_thread_not_in_the_request(self):
        import threading

        done = threading.Event()
        seen = {}
        task = mock.Mock(name="task")
        task.name = "t"

        def apply(args, kwargs):
            seen["thread"] = threading.current_thread().name
            done.set()

        task.apply.side_effect = apply
        tasking.enqueue(task, "a")
        self.assertTrue(done.wait(5))
        self.assertEqual(seen["thread"], "task:t")
        task.apply_async.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, BACKGROUND_EAGER_TASKS=False)
    def test_disabled_keeps_tasks_inline(self):
        task = mock.Mock(name="task")
        tasking.enqueue(task, "a")
        task.apply_async.assert_called_once()
