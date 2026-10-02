"""
Firebase sign-in: token verification, account mapping, and Bearer auth on protected requests.

    ./test.sh db lipaidox.auth.tests_firebase_auth

Firebase itself is never called — `firebase_auth.verify_id_token` / `FirebaseAuthService.verify`
are patched — so these run offline and need no service account.
"""
import base64
import json
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings
from firebase_admin import auth as firebase_auth

from lipaidox.auth.googleOuth import googleOuth
from lipaidox.auth.googleOuth.googleOuth import (
    FirebaseAuthService,
    FirebaseTokenError,
    normalize_private_key,
    service_account_from_env,
)
from lipaidox.auth.jwt_auth import generate_access_token
from lipaidox.auth.models import User
from lipaidox.models import Tenant

PEM = "-----BEGIN PRIVATE KEY-----\nMIIEabc\nxyz=\n-----END PRIVATE KEY-----\n"


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def fake_firebase_jwt(project="lipaidox-platform") -> str:
    """Shaped like a Firebase ID token (issuer is what routes it); never verified for real here."""
    return f"{_b64({'alg': 'RS256'})}.{_b64({'iss': f'https://securetoken.google.com/{project}'})}.sig"


def firebase_claims(uid="fb-uid-1", sub="google-sub-1", email="ann@example.com", provider="google.com", **extra):
    return {
        "uid": uid,
        "email": email,
        "email_verified": True,
        "name": "Ann Example",
        "firebase": {"sign_in_provider": provider, "identities": {"google.com": [sub]} if sub else {}},
        **extra,
    }


class PrivateKeyEnvTests(SimpleTestCase):
    def test_escaped_newlines_and_quotes_become_pem(self):
        raw = '"' + PEM.replace("\n", "\\n") + '"'
        self.assertEqual(normalize_private_key(raw), PEM)

    def test_real_newlines_are_kept(self):
        self.assertEqual(normalize_private_key(PEM), PEM)

    @override_settings(
        FIREBASE_PROJECT_ID="lipaidox-platform",
        FIREBASE_CLIENT_EMAIL="sa@lipaidox-platform.iam.gserviceaccount.com",
        FIREBASE_PRIVATE_KEY=PEM.replace("\n", "\\n"),
    )
    def test_env_triple_builds_service_account(self):
        account = service_account_from_env()
        self.assertEqual(account["project_id"], "lipaidox-platform")
        self.assertEqual(account["private_key"], PEM)
        self.assertEqual(account["type"], "service_account")

    @override_settings(FIREBASE_PROJECT_ID="p", FIREBASE_CLIENT_EMAIL="sa@p", FIREBASE_PRIVATE_KEY="not-a-key")
    def test_garbage_key_is_rejected(self):
        self.assertIsNone(service_account_from_env())

    @override_settings(FIREBASE_CLIENT_EMAIL="", FIREBASE_PRIVATE_KEY="")
    def test_unset_means_no_env_credentials(self):
        self.assertIsNone(service_account_from_env())

    def test_key_from_another_project_is_ignored(self):
        svc = FirebaseAuthService()
        with self.assertLogs(googleOuth.logger, "ERROR"):
            self.assertIsNone(svc._accept({"project_id": "com252-ffed4"}, "file", "lipaidox-platform"))
        self.assertIsNotNone(svc._accept({"project_id": "lipaidox-platform"}, "file", "lipaidox-platform"))


@override_settings(FIREBASE_CHECK_REVOKED=True, FIREBASE_ALLOW_TEST_TOKENS=False)
class VerifyErrorMappingTests(SimpleTestCase):
    """Each Firebase failure becomes a short, client-safe message — never the SDK's text."""

    def verify_raising(self, exc):
        svc = FirebaseAuthService()
        with mock.patch.object(FirebaseAuthService, "_initialize"), mock.patch.object(
            FirebaseAuthService, "initialized", new_callable=mock.PropertyMock, return_value=True
        ), mock.patch.object(googleOuth.firebase_auth, "verify_id_token", side_effect=exc) as verify:
            with self.assertRaises(FirebaseTokenError) as ctx:
                svc.verify("a.b.c")
        return str(ctx.exception), verify

    def test_expired(self):
        msg, verify = self.verify_raising(firebase_auth.ExpiredIdTokenError("expired", cause=None))
        self.assertIn("expired", msg)
        self.assertTrue(verify.call_args.kwargs["check_revoked"])

    def test_revoked(self):
        msg, _ = self.verify_raising(firebase_auth.RevokedIdTokenError("revoked"))
        self.assertIn("revoked", msg)

    def test_disabled(self):
        msg, _ = self.verify_raising(firebase_auth.UserDisabledError("disabled"))
        self.assertIn("disabled", msg)

    def test_invalid(self):
        msg, _ = self.verify_raising(firebase_auth.InvalidIdTokenError("bad sig"))
        self.assertEqual(msg, "Invalid sign-in token. Please sign in again.")

    def test_malformed(self):
        msg, _ = self.verify_raising(ValueError("not a jwt"))
        self.assertIn("Invalid sign-in token", msg)

    def test_missing_token(self):
        with self.assertRaises(FirebaseTokenError):
            FirebaseAuthService().verify("   ")

    def test_not_configured(self):
        with mock.patch.object(FirebaseAuthService, "_initialize"), mock.patch.object(
            FirebaseAuthService, "initialized", new_callable=mock.PropertyMock, return_value=False
        ):
            with self.assertRaises(FirebaseTokenError) as ctx:
                FirebaseAuthService().verify("a.b.c")
        self.assertIn("not available", str(ctx.exception))

    @override_settings(DEBUG=True)
    def test_test_token_needs_explicit_opt_in(self):
        with mock.patch.object(FirebaseAuthService, "_initialize"), mock.patch.object(
            FirebaseAuthService, "initialized", new_callable=mock.PropertyMock, return_value=False
        ):
            with self.assertRaises(FirebaseTokenError):
                FirebaseAuthService().verify("test-google-token")


GOOGLE_AUTH = "mutation($t: String!) { googleAuth(idToken: $t) { accessToken refreshToken tokenType } }"
ME = "{ me { id email } }"


class GraphQLCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test", domain="firebase-tests.local")
        self.client = Client(HTTP_X_TENANT_ID=str(self.tenant.id))

    def gql(self, query, variables=None, **headers):
        res = self.client.post(
            "/graphql/", json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json", **headers,
        )
        return res.json()

    def error(self, body):
        return body["errors"][0]["message"]


class GoogleAuthFirebaseTests(GraphQLCase):

    def google_auth(self, claims=None, side_effect=None):
        with mock.patch.object(FirebaseAuthService, "verify", return_value=claims, side_effect=side_effect):
            return self.gql(GOOGLE_AUTH, {"t": fake_firebase_jwt()})

    # ── account mapping ──────────────────────────────────────────────────────

    def test_new_google_user_is_created_with_both_ids(self):
        body = self.google_auth(firebase_claims())
        self.assertEqual(body["data"]["googleAuth"]["tokenType"], "Bearer")
        user = User.objects.get(email="ann@example.com")
        self.assertEqual((user.firebase_uid, user.google_id), ("fb-uid-1", "google-sub-1"))
        self.assertTrue(user.email_verified)
        self.assertFalse(user.has_usable_password())

    def test_second_sign_in_returns_same_user(self):
        self.google_auth(firebase_claims())
        self.google_auth(firebase_claims())
        self.assertEqual(User.objects.filter(email="ann@example.com").count(), 1)

    def test_existing_mobile_user_keyed_by_google_sub_is_found(self):
        """Users made by the old native flow stored Google's `sub` — Firebase must find them."""
        old = User.objects.create(username="ann", email="ann@example.com", tenant=self.tenant,
                                  google_id="google-sub-1", auth_provider="google")
        body = self.google_auth(firebase_claims())
        self.assertNotIn("errors", body)
        old.refresh_from_db()
        self.assertEqual(old.firebase_uid, "fb-uid-1")
        self.assertEqual(User.objects.filter(email="ann@example.com").count(), 1)

    def test_existing_web_user_keyed_by_firebase_uid_is_normalised(self):
        """The web flow used to store the Firebase uid in `google_id`."""
        old = User.objects.create(username="ann", email="ann@example.com", tenant=self.tenant,
                                  google_id="fb-uid-1", auth_provider="google")
        self.assertNotIn("errors", self.google_auth(firebase_claims()))
        old.refresh_from_db()
        self.assertEqual((old.firebase_uid, old.google_id), ("fb-uid-1", "google-sub-1"))

    def test_password_account_with_same_email_is_not_taken_over(self):
        User.objects.create_user(username="ann", email="ann@example.com", password="Secret!234", tenant=self.tenant)
        body = self.google_auth(firebase_claims())
        self.assertIn("already registered with a password", self.error(body))

    def test_email_linked_to_another_google_account_conflicts(self):
        User.objects.create(username="ann", email="ann@example.com", tenant=self.tenant, google_id="someone-else")
        body = self.google_auth(firebase_claims())
        self.assertIn("different Google account", self.error(body))

    def test_non_google_firebase_provider_is_refused(self):
        body = self.google_auth(firebase_claims(provider="password", sub=None))
        self.assertIn("did not come from Google", self.error(body))
        self.assertFalse(User.objects.filter(email="ann@example.com").exists())

    def test_unverified_email_is_refused(self):
        body = self.google_auth(firebase_claims(email_verified=False))
        self.assertIn("must be verified", self.error(body))

    def test_rejected_token_message_reaches_client(self):
        body = self.google_auth(side_effect=FirebaseTokenError("Your sign-in expired. Please sign in again."))
        self.assertEqual(self.error(body), "Your sign-in expired. Please sign in again.")

    def test_inactive_local_user_cannot_sign_in(self):
        User.objects.create(username="ann", email="ann@example.com", tenant=self.tenant,
                            google_id="google-sub-1", firebase_uid="fb-uid-1", is_active=False)
        self.assertIn("deactivated", self.error(self.google_auth(firebase_claims())))

    def test_missing_token(self):
        self.assertIn("Missing", self.error(self.gql(GOOGLE_AUTH, {"t": "  "})))

    # ── protected requests ───────────────────────────────────────────────────

    def test_issued_access_token_authenticates_protected_query(self):
        access = self.google_auth(firebase_claims())["data"]["googleAuth"]["accessToken"]
        me = self.gql(ME, HTTP_AUTHORIZATION=f"Bearer {access}")["data"]["me"]
        self.assertEqual(me["email"], "ann@example.com")

    def test_missing_malformed_and_invalid_bearer_are_anonymous(self):
        user = User.objects.create(username="bob", email="bob@example.com", tenant=self.tenant)
        good = generate_access_token(user)
        for header in (None, "Bearer", "Bearer ", f"Token {good}", "Bearer not.a.jwt", f"Bearer {good}x"):
            extra = {"HTTP_AUTHORIZATION": header} if header is not None else {}
            self.assertIsNone(self.gql(ME, **extra)["data"]["me"], header)
        self.assertEqual(self.gql(ME, HTTP_AUTHORIZATION=f"bearer {good}")["data"]["me"]["email"], "bob@example.com")

    def test_firebase_id_token_is_not_an_api_session_token(self):
        """Only our own JWT authenticates requests — a Firebase token must go through googleAuth."""
        self.assertIsNone(self.gql(ME, HTTP_AUTHORIZATION=f"Bearer {fake_firebase_jwt()}")["data"]["me"])

    def test_deactivated_user_token_stops_working(self):
        user = User.objects.create(username="bob", email="bob@example.com", tenant=self.tenant)
        token = generate_access_token(user)
        User.objects.filter(pk=user.pk).update(is_active=False)
        self.assertIsNone(self.gql(ME, HTTP_AUTHORIZATION=f"Bearer {token}")["data"]["me"])

    def test_expired_access_token_is_anonymous(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        from django.conf import settings

        user = User.objects.create(username="bob", email="bob@example.com", tenant=self.tenant)
        expired = jwt.encode(
            {"user_id": str(user.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            settings.JWT_SECRET_KEY, algorithm="HS256",
        )
        self.assertIsNone(self.gql(ME, HTTP_AUTHORIZATION=f"Bearer {expired}")["data"]["me"])


SIGN_IN = """mutation($t: String!) { googleSignIn(idToken: $t) {
  status email firstName lastName auth { accessToken tokenType } } }"""
COMPLETE = """mutation($t: String!, $i: GoogleSignupInput!) {
  completeGoogleSignup(idToken: $t, input: $i) { accessToken username email } }"""


class GoogleSignupFlowTests(GraphQLCase):
    """googleSignIn creates the account itself. completeGoogleSignup is kept working
    for builds older than that change, so both paths are covered here."""

    def call(self, query, claims, variables=None):
        with mock.patch.object(FirebaseAuthService, "verify", return_value=claims):
            return self.gql(query, {"t": fake_firebase_jwt(), **(variables or {})})

    def form(self, **over):
        return {"i": {"username": "ann_x", "password": "Str0ng!Pass", "firstName": "Ann",
                      "lastName": "Example", "dateOfBirth": "1995-04-02", **over}}

    def test_new_email_is_created_and_signed_into_in_one_step(self):
        res = self.call(SIGN_IN, firebase_claims())["data"]["googleSignIn"]
        self.assertEqual(res["status"], "signed_in")
        self.assertEqual(res["auth"]["tokenType"], "Bearer")

        user = User.objects.get(email="ann@example.com")
        # Username from the email, viewer role, and no password: the Google
        # identity is the only way in until they set one in Settings.
        self.assertEqual(user.username, "ann")
        self.assertEqual(user.role, "fan")
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.google_id, user.firebase_uid), ("google-sub-1", "fb-uid-1"))
        self.assertTrue(user.email_verified)
        self.assertEqual((user.first_name, user.last_name), ("Ann", "Example"))
        # No date of birth: the age gate is collected in Edit profile instead.
        self.assertIsNone(user.date_of_birth)

    def test_new_email_username_avoids_a_taken_one(self):
        User.objects.create(username="ann", email="other@example.com", tenant=self.tenant)
        self.call(SIGN_IN, firebase_claims())
        self.assertEqual(User.objects.get(email="ann@example.com").username, "ann_1")

    def test_signing_in_twice_does_not_create_a_second_account(self):
        self.call(SIGN_IN, firebase_claims())
        self.call(SIGN_IN, firebase_claims())
        self.assertEqual(User.objects.filter(email="ann@example.com").count(), 1)

    def test_existing_google_user_is_signed_in(self):
        User.objects.create(username="ann", email="ann@example.com", tenant=self.tenant,
                            google_id="google-sub-1", auth_provider="google")
        res = self.call(SIGN_IN, firebase_claims())["data"]["googleSignIn"]
        self.assertEqual(res["status"], "signed_in")
        self.assertEqual(res["auth"]["tokenType"], "Bearer")

    def test_password_account_conflict_is_reported_at_sign_in(self):
        User.objects.create_user(username="ann", email="ann@example.com", password="Secret!234", tenant=self.tenant)
        self.assertIn("already registered with a password", self.error(self.call(SIGN_IN, firebase_claims())))

    def test_completing_the_form_creates_linked_verified_account_with_password(self):
        body = self.call(COMPLETE, firebase_claims(), self.form())
        out = body["data"]["completeGoogleSignup"]
        self.assertEqual((out["username"], out["email"]), ("ann_x", "ann@example.com"))
        user = User.objects.get(email="ann@example.com")
        self.assertEqual((user.google_id, user.firebase_uid), ("google-sub-1", "fb-uid-1"))
        self.assertTrue(user.email_verified)
        self.assertTrue(user.check_password("Str0ng!Pass"))
        self.assertEqual(str(user.date_of_birth), "1995-04-02")
        # Afterwards the same Google account signs straight in.
        self.assertEqual(self.call(SIGN_IN, firebase_claims())["data"]["googleSignIn"]["status"], "signed_in")

    def test_email_comes_from_token_not_the_form(self):
        self.call(COMPLETE, firebase_claims(email="real@example.com"), self.form())
        self.assertTrue(User.objects.filter(email="real@example.com").exists())

    def test_form_rules_match_normal_signup(self):
        User.objects.create(username="taken", email="t@example.com", tenant=self.tenant)
        self.assertIn("already taken", self.error(self.call(COMPLETE, firebase_claims(), self.form(username="taken"))))
        self.assertIn("eligible", self.error(self.call(COMPLETE, firebase_claims(), self.form(dateOfBirth="2015-01-01"))))
        self.assertTrue(self.error(self.call(COMPLETE, firebase_claims(), self.form(password="short"))))
        self.assertFalse(User.objects.filter(email="ann@example.com").exists())

    def test_double_submit_signs_into_the_same_account(self):
        self.call(COMPLETE, firebase_claims(), self.form())
        again = self.call(COMPLETE, firebase_claims(), self.form(username="other_name"))
        self.assertEqual(again["data"]["completeGoogleSignup"]["username"], "ann_x")
        self.assertEqual(User.objects.filter(email="ann@example.com").count(), 1)

    def test_rejected_token_blocks_completion(self):
        with mock.patch.object(FirebaseAuthService, "verify", side_effect=FirebaseTokenError("Your sign-in expired. Please sign in again.")):
            body = self.gql(COMPLETE, {"t": fake_firebase_jwt(), **self.form()})
        self.assertIn("expired", self.error(body))
        self.assertFalse(User.objects.filter(email="ann@example.com").exists())
