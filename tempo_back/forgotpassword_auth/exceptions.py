class ForgotPasswordAuthError(Exception):
    """Base error for forgotpassword_auth (map to GraphQL messages in your API layer)."""


class UserNotFoundError(ForgotPasswordAuthError):
    pass


class InvalidOtpError(ForgotPasswordAuthError):
    pass


class OtpExpiredOrConsumedError(ForgotPasswordAuthError):
    pass


class WeakPasswordError(ForgotPasswordAuthError):
    pass


class AccountBlockedError(ForgotPasswordAuthError):
    pass


class AlreadyHasPasswordError(ForgotPasswordAuthError):
    """Initial-password OTP requested but user already has a backend password."""

    pass


class NoPasswordYetError(ForgotPasswordAuthError):
    """Forgot-password flow requested for a Google-only account with no backend password."""

    pass


class EmailMismatchError(ForgotPasswordAuthError):
    pass


class RateLimitedError(ForgotPasswordAuthError):
    pass
