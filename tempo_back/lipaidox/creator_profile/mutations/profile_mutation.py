import strawberry
from django.db import transaction
from ..models import CreatorProfile, is_username_available, reserve_username, release_username
from ..schema.profile_schema import CreatorProfileType, CreateProfileInput, UpdateProfileInput
from lipaidox.auth.permissions import UserRoles

@strawberry.type
class ProfileMutation:
    @strawberry.mutation
    def create_profile(self, info: strawberry.types.Info, input: CreateProfileInput) -> CreatorProfileType:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user has creator role
        if user.role != UserRoles.CREATOR:
            raise Exception("Creator access required")

        # Use the user's tenant instead of get_current_tenant()
        tenant = user.tenant
        
        # Check username availability using the new system
        if not is_username_available(input.username, tenant):
            raise Exception("Username already taken in this platform.")

        with transaction.atomic():
            profile = CreatorProfile.objects.create(
                user=user,
                tenant=tenant,
                username=input.username,
                bio=input.bio
            )
            # Reserve the username in history
            reserve_username(input.username, user, tenant)
        return CreatorProfileType.from_model(profile)

    @strawberry.mutation
    def update_profile(self, info: strawberry.types.Info, input: UpdateProfileInput) -> CreatorProfileType:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user has creator role
        if user.role != UserRoles.CREATOR:
            raise Exception("Creator access required")

        tenant = user.tenant

        try:
            profile = CreatorProfile.objects.get(user=user)
        except CreatorProfile.DoesNotExist:
            # Onboarding / clients may call update_profile before create_profile; materialize the row once.
            candidate = (input.username or user.username or "").strip()
            if not candidate:
                raise Exception(
                    "No creator profile exists yet. Provide a username in your profile setup, "
                    "or call create_profile first."
                )
            if not is_username_available(candidate, tenant):
                raise Exception("Username already taken in this platform.")
            with transaction.atomic():
                profile = CreatorProfile.objects.create(
                    user=user,
                    tenant=tenant,
                    username=candidate,
                    bio=input.bio or "",
                )
                reserve_username(candidate, user, tenant)

        with transaction.atomic():
            # Handle username change with recycling
            if input.username and input.username != profile.username:
                # Check if new username is available
                if not is_username_available(input.username, tenant, exclude_user=user):
                    raise Exception("Username already taken in this platform.")
                
                # Release old username back to available pool
                old_username = profile.username
                release_username(old_username, tenant)
                
                # Reserve new username
                reserve_username(input.username, user, tenant)
                
                # Update profile
                profile.username = input.username
            
            if input.bio is not None:
                profile.bio = input.bio
            if input.profilePhotoUrl is not None:
                profile.profile_photo_url = input.profilePhotoUrl
            if input.coverPhotoUrl is not None:
                profile.cover_photo_url = input.coverPhotoUrl
            if input.websiteUrl is not None:
                profile.website_url = input.websiteUrl
            if input.countryOfResidence is not None:
                profile.country_of_residence = input.countryOfResidence
            if input.city is not None:
                profile.city = input.city
            if input.nationality is not None:
                profile.nationality = input.nationality
            if input.gender is not None:
                profile.gender = input.gender
            if input.areaOfInterest is not None:
                profile.area_of_interest = input.areaOfInterest
            if input.preferredLanguage is not None:
                profile.preferred_language = input.preferredLanguage
            if input.timezone is not None:
                profile.timezone = input.timezone

            if input.socialInstagram is not None:
                raw = input.socialInstagram.strip()
                if raw:
                    # Normalize bare handle (@user or user) to full URL
                    if not raw.startswith("http"):
                        handle = raw.lstrip("@")
                        raw = f"https://www.instagram.com/{handle}/"
                    profile.social_instagram = raw[:255]
                else:
                    profile.social_instagram = None

            profile.save()
        return CreatorProfileType.from_model(profile)

    @strawberry.mutation
    def follow_user(self, info: strawberry.types.Info, user_id: strawberry.ID) -> bool:
        from ..models.follow import Follow
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        if str(user.id) == str(user_id):
            raise Exception("Cannot follow yourself")
        from lipaidox.auth.models import User
        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise Exception("User not found")
        _, created = Follow.objects.get_or_create(
            follower=user, followed=target, tenant=user.tenant
        )
        if created:
            try:
                profile = target.profile
                profile.follower_count = Follow.objects.filter(followed=target).count()
                profile.save(update_fields=["follower_count"])
            except Exception:
                pass
        return True

    @strawberry.mutation
    def unfollow_user(self, info: strawberry.types.Info, user_id: strawberry.ID) -> bool:
        from ..models.follow import Follow
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        deleted, _ = Follow.objects.filter(follower=user, followed_id=user_id).delete()
        if deleted:
            from lipaidox.auth.models import User
            try:
                target = User.objects.get(id=user_id)
                profile = target.profile
                profile.follower_count = Follow.objects.filter(followed=target).count()
                profile.save(update_fields=["follower_count"])
            except Exception:
                pass
        return True
