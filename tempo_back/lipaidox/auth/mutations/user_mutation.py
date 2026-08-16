import re
import uuid

import strawberry
from typing import Optional

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone

from ..models import User, RefreshToken
from ..schema.user_schema import UserType, UserInput, UserUpdateInput, UserSelfUpdateInput
from ..schema.token_schema import AuthPayload, AuthTokenType
from ..jwt_auth import (
    generate_access_token,
    generate_refresh_token,
    hash_token,
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
)
from ..googleauth import (
    FirebaseAuthService,
    normalize_google_id_token,
    peek_google_jwt_issuer,
    verify_google_credential_jwt,
)
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_admin, UserRoles
from lipaidox.auth.validation import normalize_signup_email, validate_signup_password
from lipaidox.auth.user_eligibility import (
    assert_user_may_authenticate,
    email_already_registered,
    find_user_by_email_tenant,
)
from lipaidox.creator_profile.models import (
    CreatorProfile,
    is_username_available,
    reserve_username,
)


def _issue_auth_payload(info: strawberry.types.Info, user: User) -> AuthPayload:
    tenant = get_current_tenant()
    if user.tenant_id != tenant.id:
        raise Exception("User does not belong to this tenant.")
    assert_user_may_authenticate(user)
    access_token = generate_access_token(user)
    raw_refresh = generate_refresh_token()
    token_hash = hash_token(raw_refresh)
    RefreshToken.objects.create(
        user=user,
        tenant=tenant,
        token_hash=token_hash,
        device_name=info.context.request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    return AuthPayload(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="Bearer",
        expires_in=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        user_id=strawberry.ID(str(user.id)),
        username=user.username,
        email=user.email,
        role=user.role,
        first_name=(getattr(user, "first_name", None) or "")[:150],
        last_name=(getattr(user, "last_name", None) or "")[:150],
    )


def _google_username_stem(local_part: str) -> str:
    s = re.sub(r"[^a-z0-9_]", "", (local_part or "user").lower())
    return (s[:30] if s else "user")[:150]


def _unique_username_for_tenant(local_part: str, tenant) -> str:
    base = _google_username_stem(local_part)
    candidate = base
    n = 0
    while User.objects.filter(username=candidate, tenant=tenant).exists():
        n += 1
        suffix = f"_{n}" if n < 10000 else f"_{uuid.uuid4().hex[:8]}"
        room = max(1, 150 - len(suffix))
        stem = base[:room]
        candidate = f"{stem}{suffix}"[:150]
    return candidate


def _split_display_name(name: Optional[str]) -> tuple[str, str]:
    if not name or not str(name).strip():
        return "", ""
    parts = str(name).strip().split(None, 1)
    given = (parts[0] or "")[:150]
    family = (parts[1] or "")[:150] if len(parts) > 1 else ""
    return given, family


@strawberry.type
class UserMutation:
    @strawberry.mutation
    def login_user(
        self, info: strawberry.types.Info, username: str, password: str
    ) -> AuthPayload:
        tenant = get_current_tenant()
        req = info.context.request
        raw = (username or "").strip()
        user = authenticate(
            request=req,
            username=raw,
            password=password,
        )
        if not user and "@" in raw:
            try:
                by_email = find_user_by_email_tenant(
                    normalize_signup_email(raw), tenant.id
                )
            except Exception:
                by_email = None
            if by_email:
                user = authenticate(
                    request=req,
                    username=by_email.username,
                    password=password,
                )
        if not user:
            hint = User.objects.filter(username__iexact=raw, tenant=tenant).first()
            if not hint and "@" in raw:
                try:
                    hint = find_user_by_email_tenant(
                        normalize_signup_email(raw), tenant.id
                    )
                except Exception:
                    hint = None
            if hint is not None and not hint.has_usable_password():
                raise Exception(
                    "This account uses Google or Firebase sign-in. Use that option instead of "
                    "username and password."
                )
            raise Exception("Invalid username or password.")
        if user.tenant != tenant:
            raise Exception("User does not belong to this tenant.")
        payload = _issue_auth_payload(info, user)
        if user.is_first_login:
            User.objects.filter(pk=user.pk).update(is_first_login=False)
        return payload

    @strawberry.mutation
    def register_user(
        self, info: strawberry.types.Info, input: UserInput
    ) -> AuthPayload:
        """
        Single-step signup: creates the account and returns JWT tokens.
        """
        tenant = get_current_tenant()

        if input.role and input.role not in [UserRoles.FAN, UserRoles.CREATOR]:
            raise Exception(
                f"Invalid role. Must be '{UserRoles.FAN}' or '{UserRoles.CREATOR}'."
            )

        normalized_email = normalize_signup_email(input.email)
        validate_signup_password(input.password)

        if User.objects.filter(username=input.username, tenant=tenant).exists():
            raise Exception("Username already taken.")
        if email_already_registered(normalized_email, tenant.id):
            raise Exception(
                "This email is already registered. Sign in or use forgot password."
            )

        with transaction.atomic():
            user = User.objects.create_user(
                username=input.username,
                email=normalized_email,
                password=input.password,
                role=input.role or UserRoles.FAN,
                tenant=tenant,
            )

        return _issue_auth_payload(info, user)

    @strawberry.mutation
    def refresh_access_token(
        self, info: strawberry.types.Info, refresh_token: str
    ) -> AuthTokenType:
        token_hash = hash_token(refresh_token)
        try:
            record = RefreshToken.objects.select_related("user").get(
                token_hash=token_hash, status="active"
            )
        except RefreshToken.DoesNotExist:
            raise Exception("Invalid or expired refresh token.")

        if record.expires_at < timezone.now():
            record.status = "expired"
            record.save(update_fields=["status"])
            raise Exception("Refresh token has expired. Please log in again.")

        record.last_used_at = timezone.now()
        record.save(update_fields=["last_used_at"])

        new_access = generate_access_token(record.user)
        return AuthTokenType(
            access_token=new_access,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        )

    @strawberry.mutation
    def logout_user(self, info: strawberry.types.Info, refresh_token: str) -> bool:
        token_hash = hash_token(refresh_token)
        RefreshToken.objects.filter(token_hash=token_hash).update(status="revoked")
        return True

    @strawberry.mutation
    def google_auth(
        self,
        info: strawberry.types.Info,
        id_token: str,
        signup_role: Optional[str] = None,
    ) -> AuthPayload:
        """
        Sign in or register with Google.

        **Firebase modality:** if `FIREBASE_PROJECT_ID` (+ Admin SDK) is configured and the
        token is a Firebase ID token, it is verified with Firebase Admin first.

        **GIS modality:** Google Identity Services JWT (`iss` from accounts.google.com) is
        verified with `verify_google_credential_jwt` — not sent through Firebase first.
        """
        tenant = get_current_tenant()

        normalized = normalize_google_id_token(id_token)
        if not normalized:
            raise Exception("Missing Google credential.")

        iss = peek_google_jwt_issuer(normalized) or ""
        fb = FirebaseAuthService()

        # Firebase ID tokens use https://securetoken.google.com/<projectId> — do not run
        # those through GIS verification (wrong audience and misleading errors).
        if "securetoken.google.com" in iss:
            fb_claims = fb.verify_token(normalized)
            if not fb_claims:
                msg = "Invalid or expired Firebase sign-in. Please try again."
                if settings.DEBUG:
                    hint = getattr(fb, "last_verify_error", None)
                    if hint:
                        msg = f"{msg} (dev: {hint})"
                raise Exception(msg)
        else:
            fb_claims = None

        if fb_claims:
            sub = fb_claims.get("uid")
            email_raw = fb_claims.get("email")
            email_verified = bool(fb_claims.get("email_verified"))
            given, family = _split_display_name(fb_claims.get("name"))
            if not sub:
                raise Exception("Invalid Firebase account response.")
            if not email_raw:
                raise Exception("Firebase did not return an email for this account.")
            if not email_verified:
                raise Exception(
                    "Your Google email must be verified before you can use it to sign in."
                )
            normalized_email = normalize_signup_email(email_raw)
        else:
            try:
                claims = verify_google_credential_jwt(normalized)
            except ValueError as e:
                raise Exception(str(e)) from e
            sub = claims.get("sub")
            if not sub:
                raise Exception("Invalid Google account response.")
            email_raw = claims.get("email")
            if not email_raw:
                raise Exception("Google did not return an email for this account.")
            if not claims.get("email_verified", False):
                raise Exception(
                    "Your Google email must be verified before you can use it to sign in."
                )
            normalized_email = normalize_signup_email(email_raw)
            given = (claims.get("given_name") or "")[:150]
            family = (claims.get("family_name") or "")[:150]

        role = UserRoles.FAN
        if signup_role is not None and str(signup_role).strip():
            sr = str(signup_role).strip().lower()
            if sr not in (UserRoles.FAN, UserRoles.CREATOR):
                raise Exception(
                    f"Invalid role for Google sign-up. Must be '{UserRoles.FAN}' or '{UserRoles.CREATOR}'."
                )
            role = sr

        with transaction.atomic():
            user = User.objects.filter(google_id=sub, tenant=tenant).first()
            if user:
                return _issue_auth_payload(info, user)

            existing = find_user_by_email_tenant(normalized_email, tenant.id)
            if existing:
                if existing.google_id and existing.google_id != sub:
                    raise Exception(
                        "This email is linked to a different Google account. "
                        "Use that Google account or contact support."
                    )
                if existing.apple_id and not existing.google_id:
                    raise Exception(
                        "This email is already linked to Apple sign-in. Use that method to continue."
                    )
                if existing.has_usable_password() and not existing.google_id:
                    raise Exception(
                        "This email is already registered with a password. Sign in with your "
                        "username and password, or use Forgot password."
                    )
                existing.google_id = sub
                existing.auth_provider = "google"
                existing.email_verified = True
                if given:
                    existing.first_name = given
                if family:
                    existing.last_name = family
                existing.save(
                    update_fields=[
                        "google_id",
                        "auth_provider",
                        "email_verified",
                        "first_name",
                        "last_name",
                    ]
                )
                return _issue_auth_payload(info, existing)

            local_part = normalized_email.split("@", 1)[0]
            username = _unique_username_for_tenant(local_part, tenant)
            new_user = User(
                username=username,
                email=normalized_email,
                tenant=tenant,
                role=role,
                auth_provider="google",
                google_id=sub,
                email_verified=True,
                first_name=given,
                last_name=family,
            )
            new_user.set_unusable_password()
            new_user.save()
            return _issue_auth_payload(info, new_user)

    @strawberry.mutation
    def create_user(self, info: strawberry.types.Info, input: UserInput) -> UserType:
        tenant = get_current_tenant()

        if input.role and input.role not in [
            UserRoles.FAN,
            UserRoles.CREATOR,
            UserRoles.ADMIN,
        ]:
            raise Exception(
                f"Invalid role. Must be one of: {UserRoles.FAN}, {UserRoles.CREATOR}, {UserRoles.ADMIN}"
            )

        current_user = info.context.request.user
        if input.role == UserRoles.ADMIN and (
            not current_user.is_authenticated or current_user.role != UserRoles.ADMIN
        ):
            raise Exception("Only admins can create admin users")

        if User.objects.filter(username=input.username, tenant=tenant).exists():
            raise Exception("Username already exists in this tenant.")

        normalized_email = normalize_signup_email(input.email)
        validate_signup_password(input.password)

        # Age gate (16+). Enforced here so a tampered frontend can't bypass it.
        dob = getattr(input, "dateOfBirth", None)
        if dob is not None:
            from datetime import date as _date
            today = _date.today()
            if dob > today:
                raise Exception("Date of birth cannot be in the future.")
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 16:
                raise Exception("Your age is not eligible to use this app.")

        if email_already_registered(normalized_email, tenant.id):
            raise Exception(
                "This email is already registered. Sign in or use forgot password."
            )

        with transaction.atomic():
            user = User.objects.create_user(
                username=input.username,
                email=normalized_email,
                password=input.password,
                role=input.role or UserRoles.FAN,
                tenant=tenant,
            )
            # Persist the optional profile fields collected at signup.
            update_fields = []
            if getattr(input, "firstName", None):
                user.first_name = input.firstName.strip()
                update_fields.append("first_name")
            if getattr(input, "lastName", None):
                user.last_name = input.lastName.strip()
                update_fields.append("last_name")
            if dob is not None:
                user.date_of_birth = dob
                update_fields.append("date_of_birth")
            if update_fields:
                user.save(update_fields=update_fields)

        return UserType.from_model(user)

    @strawberry.mutation
    @require_admin
    def update_user(
        self,
        info: strawberry.types.Info,
        user_id: strawberry.ID,
        input: UserUpdateInput,
    ) -> Optional[UserType]:
        tenant = get_current_tenant()
        try:
            user = User.objects.get(id=user_id, tenant=tenant)
            if input.email:
                user.email = input.email
            if input.role:
                user.role = input.role
            if input.status:
                user.status = input.status
            user.save()
            return UserType.from_model(user)
        except User.DoesNotExist:
            return None

    @strawberry.mutation
    @require_admin
    def delete_user(self, info: strawberry.types.Info, user_id: strawberry.ID) -> bool:
        tenant = get_current_tenant()
        try:
            user = User.objects.get(id=user_id, tenant=tenant)
            user.delete()
            return True
        except User.DoesNotExist:
            return False

    @strawberry.mutation
    def update_me(self, info: strawberry.types.Info, input: UserSelfUpdateInput) -> UserType:
        """Authenticated user updates their own account. Email change clears email_verified."""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required.")

        update_fields: list[str] = []

        if input.first_name is not None:
            user.first_name = input.first_name.strip()[:150]
            update_fields.append("first_name")

        if input.last_name is not None:
            user.last_name = input.last_name.strip()[:150]
            update_fields.append("last_name")

        if input.phone_number is not None:
            user.phone_number = input.phone_number.strip()[:20] or None
            update_fields.append("phone_number")

        if input.phone_country_code is not None:
            user.phone_country_code = input.phone_country_code.strip()[:10] or None
            update_fields.append("phone_country_code")

        if input.date_of_birth is not None:
            user.date_of_birth = input.date_of_birth
            update_fields.append("date_of_birth")

        if input.email is not None:
            from lipaidox.auth.validation import normalize_signup_email
            from lipaidox.auth.user_eligibility import email_already_registered, find_user_by_email_tenant
            new_email = normalize_signup_email(input.email)
            tenant = get_current_tenant()
            # Only apply if actually different
            if new_email != normalize_signup_email(user.email):
                existing = find_user_by_email_tenant(new_email, tenant.id)
                if existing and str(existing.pk) != str(user.pk):
                    raise Exception("That email address is already in use by another account.")
                with transaction.atomic():
                    user.email = new_email
                    # Changing email requires re-verification
                    user.email_verified = False
                    update_fields += ["email", "email_verified"]
                    if update_fields:
                        user.save(update_fields=list(set(update_fields)))
                return UserType.from_model(user)

        if update_fields:
            user.save(update_fields=update_fields)
        return UserType.from_model(user)

    @strawberry.mutation
    def upgrade_account_to_creator(self, info: strawberry.types.Info) -> UserType:
        """
        Authenticated viewer (fan) may switch to creator to unlock uploads and creator APIs.

        Ensures a ``CreatorProfile`` row exists (using the account username when available).
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required.")

        tenant = get_current_tenant()
        if user.tenant_id != tenant.id:
            raise Exception("User does not belong to this tenant.")

        if user.role == UserRoles.CREATOR or user.role == UserRoles.ADMIN:
            return UserType.from_model(user)
        if user.role != UserRoles.FAN:
            raise Exception("Only viewer accounts can upgrade to creator from here.")

        with transaction.atomic():
            user.role = UserRoles.CREATOR
            user.save(update_fields=["role"])

            if not CreatorProfile.objects.filter(user=user).exists():
                candidate = (user.username or "").strip()
                if not candidate:
                    raise Exception(
                        "Your account needs a username before you can become a creator. "
                        "Update your account details first."
                    )
                if not is_username_available(candidate, tenant):
                    raise Exception(
                        "That username is already used by another creator profile. "
                        "Change your account username, then try again."
                    )
                CreatorProfile.objects.create(
                    user=user,
                    tenant=tenant,
                    username=candidate,
                    bio="",
                )
                reserve_username(candidate, user, tenant)

        return UserType.from_model(user)

    @strawberry.mutation
    def downgrade_account_to_viewer(self, info: strawberry.types.Info) -> UserType:
        """
        Creator may switch back to viewer (fan). Non-destructive: the CreatorProfile
        and any published content are kept intact so re-upgrading is instant — only
        the role flips, which hides monetization/creator tools in the client.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required.")

        tenant = get_current_tenant()
        if user.tenant_id != tenant.id:
            raise Exception("User does not belong to this tenant.")

        if user.role == UserRoles.ADMIN:
            raise Exception("Admin accounts cannot switch to viewer.")

        if user.role != UserRoles.CREATOR:
            # Already a viewer (or any non-creator) — idempotent.
            return UserType.from_model(user)

        user.role = UserRoles.FAN
        user.save(update_fields=["role"])
        return UserType.from_model(user)
