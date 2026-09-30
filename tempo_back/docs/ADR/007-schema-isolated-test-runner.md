# ADR-007 — Schema-isolated PostgreSQL test runner

- **Status:** Accepted

## Context

Django's default test runner creates a whole `test_<name>` database, which needs
`CREATEDB`. Managed/shared Postgres (and this project's dev DB user) usually lacks that
privilege, while some models (credits/live billing) use Postgres-only column types that
SQLite cannot build.

## Decision

Introduce `lipaidox_backend/test_runner.py::SchemaIsolatedRunner` (enabled via
`--settings=lipaidox_backend.test_settings`):

1. creates a **schema** inside the existing database,
2. confines `search_path` to that schema (real `public` tables are never touched),
3. migrates into it,
4. drops it afterwards (`--keepdb` keeps `lipaidox_test`).

Tests still roll back per test. `./test.sh` drives DB-free suites with `USE_SQLITE=True`
and Postgres-backed suites with this runner.

## Consequences

- (+) Works with the privileges the DB user actually has (`CREATE SCHEMA` instead of
  `CREATEDB`).
- (+) No risk of touching real data; fast repeat runs with `--keepdb`.
- (-) Postgres-only feature tests cannot run under SQLite — suite metadata must be kept
  accurate (`FAST=(…)` vs `DB=(…)` in `test.sh`).
- (-) `DROP SCHEMA ... CASCADE` on stale kept schemas requires manual cleanup when
  migrations are rewritten.