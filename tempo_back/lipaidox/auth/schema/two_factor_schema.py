import strawberry
from typing import List, Optional
from datetime import datetime


@strawberry.type
class TwoFactorStatusType:
    enabled: bool
    confirmedAt: Optional[datetime]
    backupCodesRemaining: int


@strawberry.type
class TwoFactorSetupType:
    """The manual-entry secret + the standard `otpauth://` URI (for a QR
    code, if the client renders one) — issued by `beginTwoFactorSetup`.
    Not yet enabled; `confirmTwoFactorSetup` with a valid code finishes it."""
    secret: str
    provisioningUri: str


@strawberry.type
class TwoFactorConfirmResult:
    enabled: bool
    # Shown to the user exactly once — the backend never returns plaintext
    # codes again after this call.
    backupCodes: List[str]
