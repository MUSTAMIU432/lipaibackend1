"""
Identity verification review: approval grants the badge that unlocks
subscriptions, and the eligibility row says where an application stands.

    ./test.sh db lipaidox.kyc.tests
"""
from datetime import date

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from lipaidox.auth.models import User
from lipaidox.creator_profile.models import CreatorProfile
from lipaidox.creator_profile.schema.eligibility_schema import compute_subscription_eligibility
from lipaidox.kyc.admin import KYCStatusAdmin
from lipaidox.kyc.models import DocumentStatus, KYCOverallStatus, KYCStatus, VerificationDocument
from lipaidox.kyc.services import approve_kyc, request_kyc_resubmission


class KYCReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="kyc1", email="kyc1@example.com", password="x", role="creator")
        self.profile = CreatorProfile.objects.create(user=self.user, username="kyc1")
        self.doc = VerificationDocument.objects.create(
            creator=self.profile,
            document_type="national_id",
            document_number="19900101-12345",
            document_expiry_date=date(2030, 1, 1),
            document_file_url="https://example.com/id.jpg",
            selfie_url="https://example.com/selfie.jpg",
        )
        self.kyc = KYCStatus.objects.create(
            creator=self.profile, overall_status=KYCOverallStatus.PENDING, current_document=self.doc
        )

    def authority_row(self):
        rows = compute_subscription_eligibility(self.user).requirements
        return next(r for r in rows if r.key == "authority")

    def test_pending_application_reads_under_review(self):
        row = self.authority_row()
        self.assertFalse(row.met)
        self.assertIn("under review", row.detail)

    def test_approval_grants_badge_and_meets_requirement(self):
        approve_kyc(self.kyc)
        self.profile.refresh_from_db()
        self.doc.refresh_from_db()
        self.assertTrue(self.profile.is_verified)
        self.assertEqual(self.doc.status, DocumentStatus.APPROVED)
        row = self.authority_row()
        self.assertTrue(row.met)
        self.assertIsNone(row.detail)

    def test_resubmission_request_tells_creator_to_resubmit(self):
        request_kyc_resubmission(self.kyc, note="Photo is blurry")
        self.kyc.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.kyc.overall_status, KYCOverallStatus.RESUBMISSION_REQUESTED)
        self.assertFalse(self.profile.is_verified)
        self.assertIn("resubmit", self.authority_row().detail)

    def test_nothing_submitted_invites_verification(self):
        self.kyc.delete()
        self.assertIn("Verify your identity", self.authority_row().detail)

    def test_admin_action_approves(self):
        admin_user = User.objects.create_user(username="rev", email="rev@example.com", password="x", role="admin")
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        model_admin = KYCStatusAdmin(KYCStatus, AdminSite())
        model_admin.message_user = lambda *a, **k: None
        model_admin.approve(request, KYCStatus.objects.filter(pk=self.kyc.pk))
        self.profile.refresh_from_db()
        self.kyc.refresh_from_db()
        self.assertTrue(self.profile.is_verified)
        self.assertEqual(self.kyc.reviewed_by, admin_user)
