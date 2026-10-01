"""
KYC review — the one place an identity verification is approved or sent back.

Approval is what earns the creator Lipaidox's verification badge
(`CreatorProfile.is_verified`), which the Subscriptions gate checks
(`compute_subscription_eligibility`). Before this existed nothing ever set a
KYC to approved, so the badge — and subscriptions — were unreachable.

Used by the Django admin actions (`kyc/admin.py`); kept separate so the rules
live in one place whichever surface calls them.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lipaidox.kyc.models.kyc_status import KYCOverallStatus, KYCStatus
from lipaidox.kyc.models.verification_document import DocumentStatus


def approve_kyc(kyc: KYCStatus, reviewer=None) -> KYCStatus:
    now = timezone.now()
    with transaction.atomic():
        kyc.overall_status = KYCOverallStatus.APPROVED
        kyc.reviewed_by = reviewer
        kyc.reviewed_at = now
        kyc.approved_at = now
        kyc.rejection_reason = None
        kyc.rejection_note = None
        kyc.save()
        if kyc.current_document_id:
            kyc.current_document.status = DocumentStatus.APPROVED
            kyc.current_document.save(update_fields=["status"])
        profile = kyc.creator
        if not profile.is_verified:
            profile.is_verified = True
            profile.save(update_fields=["is_verified"])
    return kyc


def request_kyc_resubmission(kyc: KYCStatus, reviewer=None, reason: str | None = None, note: str | None = None) -> KYCStatus:
    """Sends it back to the creator to fix — they can submit again from the app."""
    with transaction.atomic():
        kyc.overall_status = KYCOverallStatus.RESUBMISSION_REQUESTED
        kyc.reviewed_by = reviewer
        kyc.reviewed_at = timezone.now()
        kyc.rejection_reason = reason
        kyc.rejection_note = note
        kyc.save()
        if kyc.current_document_id:
            kyc.current_document.status = DocumentStatus.RESUBMISSION_REQUESTED
            kyc.current_document.save(update_fields=["status"])
    return kyc
