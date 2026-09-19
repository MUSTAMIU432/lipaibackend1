"""
Settings for running the test suite: the normal settings, plus the schema-isolated
runner (see `test_runner.py`). Use with `--settings=lipaidox_backend.test_settings`.
"""
from .settings import *  # noqa: F401,F403

TEST_RUNNER = "lipaidox_backend.test_runner.SchemaIsolatedRunner"
