# ADR-010 — Argon2id-first password hashing with PBKDF2 fallback

- **Status:** Accepted

## Context

Registration/login costs dominate per-auth response time (~0.5–1s CPU with stock PBKDF2 at
600k iterations; registration pays twice). PBKDF2 is the Django default and randomizes well,
but Argon2id is stronger (memory-hard) and faster on modern hardware.

## Decision

Set `PASSWORD_HASHERS` to order:
`Argon2PasswordHasher → PBKDF2PasswordHasher → PBKDF2SHA1PasswordHasher → BCryptSHA256PasswordHasher`,
with a guarded `import argon2` (`settings.py:276-289`): if `argon2-cffi` is missing, the
app boots with stock PBKDF2 behaviour and logs a warning. Old hashes still verify and
Django re-hashes to Argon2 on the next successful login.

## Consequences

- (+) Stronger, faster hashing; transparent upgrade path for existing passwords.
- (+) No hard dependency — graceful fallback if the wheel is absent.
- (-) Argon2 parameters are Django defaults (not tuned); tune when load profiling exists.
- (-) Re-hash-on-login adds a one-time CPU spike per migrating user.