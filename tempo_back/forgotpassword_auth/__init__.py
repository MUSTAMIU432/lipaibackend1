"""
Password reset (forgot) and first-time password (Google-linked, no password yet).

Copy this package to e.g. lipaidox/auth/forgotpassword_auth and wire GraphQL resolvers
to ForgotPasswordAuthService with your ORM-backed UserRepository / OtpRepository.
"""

from .exceptions import ForgotPasswordAuthError
from .service import ForgotPasswordAuthService
from .types import OtpPurpose, ServiceResult

__all__ = [
    "ForgotPasswordAuthError",
    "ForgotPasswordAuthService",
    "OtpPurpose",
    "ServiceResult",
]
