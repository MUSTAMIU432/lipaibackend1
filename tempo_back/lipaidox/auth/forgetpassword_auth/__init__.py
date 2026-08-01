"""
Forgot-password helpers used by ``lipaidox.auth`` GraphQL (OTP verify step).

Password reset email + ``resetPassword`` live in ``mutations/password_mutation.py``;
this package holds ``otp_verify`` (``verifyPasswordResetOtp``) aligned with the Next.js wizard.

Portable domain logic and unit tests live at the project root: ``forgotpassword_auth/``
(sibling of ``manage.py``), for optional refactors or alternate storage backends.
"""
