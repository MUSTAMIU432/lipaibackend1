"""
Test runner for databases where the app's user cannot `CREATE DATABASE`.

Django's default runner builds a whole `test_<name>` database, which needs that
privilege. Managed and shared Postgres setups (and this project's dev database)
usually don't grant it — but the user can create a *schema* inside its own
database. This runner does that instead:

  1. creates a schema (`lipaidox_test` when `--keepdb`, otherwise a throwaway name),
  2. points the connection's `search_path` at ONLY that schema, so no query can
     read or write the real (`public`) tables,
  3. runs the project's migrations into it, and
  4. drops the schema afterwards (unless `--keepdb`).

`TestCase` still wraps each test in a transaction that is rolled back, exactly as
with the stock runner. Use `--keepdb` while developing: the first run migrates
everything (~1–2 min), later runs only apply what changed.

Enable it with `--settings=lipaidox_backend.test_settings`, or just run `./test.sh`.
"""
import os
import re
import uuid

from django.core.management import call_command
from django.db import connections
from django.test.runner import DiscoverRunner

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
DEFAULT_SCHEMA = "lipaidox_test"


class SchemaIsolatedRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        conn = connections["default"]
        if conn.vendor != "postgresql":
            raise RuntimeError(
                "SchemaIsolatedRunner needs PostgreSQL (the schema uses Postgres-only column "
                "types). Set USE_SQLITE=False, or use the DB-free suites."
            )

        name = os.environ.get("TEST_DB_SCHEMA") or (
            DEFAULT_SCHEMA if self.keepdb else f"{DEFAULT_SCHEMA}_{uuid.uuid4().hex[:8]}"
        )
        if not _SCHEMA_NAME.match(name):
            raise RuntimeError(f"Unsafe TEST_DB_SCHEMA {name!r}: use lowercase letters, digits and underscores.")
        if name == "public":
            raise RuntimeError("Refusing to run tests in the public schema.")

        with conn.cursor() as cursor:
            try:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{name}"')
            except Exception as exc:  # noqa: BLE001 — turn a bare DB error into guidance
                raise RuntimeError(
                    f"Could not create schema {name!r} ({exc}). The database user needs CREATE "
                    "privilege on the database — or CREATEDB, in which case use the stock runner."
                ) from exc

        # Confine every later query to the test schema, then reconnect so it applies.
        conn.settings_dict.setdefault("OPTIONS", {})["options"] = f"-c search_path={name}"
        conn.close()
        self._schema = name

        if self.verbosity >= 1:
            print(f"Using isolated test schema {name!r} ({'kept' if self.keepdb else 'dropped afterwards'}).")
        call_command(
            "migrate", database="default", interactive=False, run_syncdb=True,
            verbosity=max(0, self.verbosity - 1),
        )
        return [("default", name, not self.keepdb)]

    def teardown_databases(self, old_config, **kwargs):
        conn = connections["default"]
        name = getattr(self, "_schema", None)
        if name and not self.keepdb:
            with conn.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        conn.close()
