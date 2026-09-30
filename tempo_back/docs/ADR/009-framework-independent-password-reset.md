# ADR-009 — Framework-independent password-reset package

- **Status:** Accepted (reference/embedded; live path uses the Django-ORM twin)

## Context

Password-reset/OTP logic must be unit-testable without a database or Django, and must not
accidentally couple to ORM models in tests.

## Decision

`forgotpassword_auth/` is a **framework-independent** package (no Django imports; enforced
and documented). It defines `ForgotPasswordAuthService` behind runtime-checkable protocols
(`UserRepository`, `OtpRepository`, `Mailer`), hashes OTPs with **HMAC-SHA256 + pepper**
(`otp_util.py`), enforces an anti-enumeration success shape, and is tested with plain
`unittest` and fakes (`forgotpassword_auth/tests/test_service.py`).

The GraphQL-wired flow is a parallel Django-ORM implementation
(`lipaidox/auth/mutations/password_mutation.py` + `PasswordResetOtp` + `email_outbound.py`)
that reuses the same TTL/attempt/expiry semantics but stores OTP hashes via Django password
hashers.

## Consequences

- (+) Reset logic is testable in isolation, fast, and DB-free.
- (+) Password-rule policy is explicit and versioned in code.
- (-) Two implementations to keep in sync (reference vs live) — a source of drift; a future
  phase could port the live path onto the package.
- (-) The reference package is not wired to Django today (grep shows only its tests reference
  it).