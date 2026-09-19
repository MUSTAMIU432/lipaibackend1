"""
App ratings — submit, validation, throttling, and admin review.

Postgres-backed (see test.sh):   ./test.sh db lipaidox.feedback.tests --keepdb
"""
from types import SimpleNamespace as NS

from django.test import TestCase

from lipaidox.auth.models import User
from lipaidox_backend.schema import schema

from .models import AppFeedback

SUBMIT = """mutation($r:Int!,$m:String,$v:String,$p:String,$a:String){
  submitAppFeedback(rating:$r, message:$m, appVersion:$v, platform:$p, appId:$a){ success message } }"""


def gql(user, query, variables=None):
    request = NS(user=user or NS(is_authenticated=False), META={})
    result = schema.execute_sync(query, variable_values=variables or {}, context_value=NS(request=request))
    return result.data, [str(e) for e in (result.errors or [])]


class FeedbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fan1", email="f1@example.com", password="x", role="fan")
        self.admin = User.objects.create_user(username="ad", email="ad@example.com", password="x", role="admin")

    def test_signed_in_user_can_rate_and_it_is_stored(self):
        data, errs = gql(self.user, SUBMIT, {"r": 4, "m": "  Love it  ", "v": "1.1.0", "p": "android 34", "a": "com.lipaidox"})
        self.assertEqual(errs, [])
        self.assertTrue(data["submitAppFeedback"]["success"])
        row = AppFeedback.objects.get()
        self.assertEqual((row.user_id, row.rating, row.message), (self.user.id, 4, "Love it"))   # trimmed
        self.assertEqual((row.app_version, row.platform, row.app_id), ("1.1.0", "android 34", "com.lipaidox"))

    def test_anonymous_cannot_submit(self):
        _, errs = gql(None, SUBMIT, {"r": 5})
        self.assertTrue(any("Sign in" in e for e in errs))
        self.assertEqual(AppFeedback.objects.count(), 0)

    def test_rating_must_be_one_to_five(self):
        for bad in (0, 6, -1):
            _, errs = gql(self.user, SUBMIT, {"r": bad})
            self.assertTrue(errs, bad)
        self.assertEqual(AppFeedback.objects.count(), 0)

    def test_overlong_message_is_refused(self):
        _, errs = gql(self.user, SUBMIT, {"r": 3, "m": "x" * 2001})
        self.assertTrue(any("under 2000" in e for e in errs))

    def test_daily_throttle(self):
        for _ in range(5):
            _, errs = gql(self.user, SUBMIT, {"r": 5})
            self.assertEqual(errs, [])
        _, errs = gql(self.user, SUBMIT, {"r": 5})
        self.assertTrue(any("tomorrow" in e for e in errs))
        # another user is unaffected
        other = User.objects.create_user(username="fan2", email="f2@example.com", password="x", role="fan")
        _, errs = gql(other, SUBMIT, {"r": 5})
        self.assertEqual(errs, [])

    def test_admin_summary_and_filtering(self):
        for stars in (5, 5, 4, 2, 1):
            AppFeedback.objects.create(user=self.user, rating=stars, message=f"{stars} stars")
        data, errs = gql(self.admin, "{ adminAppFeedbackSummary{ total average distribution{ stars count } } }")
        self.assertEqual(errs, [])
        s = data["adminAppFeedbackSummary"]
        self.assertEqual((s["total"], s["average"]), (5, 3.4))
        self.assertEqual([(b["stars"], b["count"]) for b in s["distribution"]], [(5, 2), (4, 1), (3, 0), (2, 1), (1, 1)])

        data, _ = gql(self.admin, "{ adminAppFeedback(maxRating: 2){ rating message username } }")
        self.assertEqual(sorted(r["rating"] for r in data["adminAppFeedback"]), [1, 2])
        self.assertEqual(data["adminAppFeedback"][0]["username"], "fan1")

    def test_review_is_admin_only(self):
        for q in ("{ adminAppFeedback{ rating } }", "{ adminAppFeedbackSummary{ total } }"):
            _, errs = gql(self.user, q)
            self.assertTrue(any("Admin access required" in e for e in errs), q)

    def test_deleting_a_user_keeps_their_feedback(self):
        AppFeedback.objects.create(user=self.user, rating=3, message="keep me")
        self.user.delete()
        self.assertEqual(AppFeedback.objects.get().message, "keep me")
