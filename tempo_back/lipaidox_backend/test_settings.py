"""
Settings for running the test suite: the normal settings, plus the schema-isolated
runner (see `test_runner.py`). Use with `--settings=lipaidox_backend.test_settings`.
"""
from .settings import *  # noqa: F401,F403

TEST_RUNNER = "lipaidox_backend.test_runner.SchemaIsolatedRunner"

# Tests never touch a real Redis. DB-backed TestCases never commit, so
# after-commit cache invalidation can't run there; a shared cache would leak
# rows between tests. Caching tests opt in to an in-memory cache explicitly.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
CELERY_BROKER_URL = ""
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = True
