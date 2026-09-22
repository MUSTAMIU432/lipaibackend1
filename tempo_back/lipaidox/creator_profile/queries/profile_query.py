import strawberry
from typing import List, Optional
from django.db import models
from ..models import CreatorProfile, is_username_available
from ..schema.profile_schema import CreatorProfileType, FollowUserType, FollowListType
from ..schema.eligibility_schema import (
    CreatorEligibilityType,
    compute_creator_eligibility,
    compute_subscription_eligibility,
)
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class ProfileQuery:
    @strawberry.field
    def my_creator_eligibility(self, info: strawberry.types.Info) -> Optional[CreatorEligibilityType]:
        """Nine real checks against the current user's own data — see
        `eligibility_schema.py` for what each one reads and why."""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        return compute_creator_eligibility(user)

    @strawberry.field
    def my_subscription_eligibility(self, info: strawberry.types.Info) -> Optional[CreatorEligibilityType]:
        """The Subscriptions setup wizard's own three-check gate — see
        `compute_subscription_eligibility` for what each one reads."""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        return compute_subscription_eligibility(user)

    @strawberry.field
    def username_available(self, info: strawberry.types.Info, username: str) -> bool:
        """Live check for the "Change username" screen — reuses the same
        `is_username_available` the `updateProfile` mutation itself enforces,
        so a green "Available" here can't disagree with what saving does."""
        user = info.context.request.user
        tenant = get_current_tenant()
        candidate = (username or "").strip()
        if len(candidate) < 3:
            return False
        exclude = user if user.is_authenticated else None
        return is_username_available(candidate, tenant, exclude_user=exclude)

    @strawberry.field
    def my_profile(self, info: strawberry.types.Info) -> Optional[CreatorProfileType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        try:
            profile = CreatorProfile.objects.get(user=user)
            return CreatorProfileType.from_model(profile)
        except CreatorProfile.DoesNotExist:
            return None

    @strawberry.field
    def profile_by_username(self, username: str) -> Optional[CreatorProfileType]:
        tenant = get_current_tenant()
        try:
            profile = CreatorProfile.objects.get(username=username, tenant=tenant)
            return CreatorProfileType.from_model(profile)
        except CreatorProfile.DoesNotExist:
            return None

    @strawberry.field
    def search_profiles(self, query: str) -> List[CreatorProfileType]:
        tenant = get_current_tenant()
        profiles = CreatorProfile.objects.filter(
            models.Q(username__icontains=query) | models.Q(bio__icontains=query),
            tenant=tenant,
            status='complete'
        )
        return [CreatorProfileType.from_model(p) for p in profiles]

    @strawberry.field
    def people_you_may_know(self, info: strawberry.types.Info, limit: int = 12) -> List[CreatorProfileType]:
        """The signup flow's "follow some people" step — real accounts,
        newest profiles first. Not a personalized recommendation (this app
        has no signal to base one on yet); it's an honest, always-populated
        default list, minus yourself and anyone you already follow. Unlike
        `search_profiles`, it doesn't filter on `status='complete'` — nothing
        in this codebase ever sets that field, so that filter would leave
        this screen empty for every user."""
        tenant = get_current_tenant()
        user = info.context.request.user
        qs = CreatorProfile.objects.filter(tenant=tenant)
        if user.is_authenticated:
            qs = qs.exclude(user=user)
            from ..models.follow import Follow
            following_ids = Follow.objects.filter(follower=user).values_list("followed_id", flat=True)
            qs = qs.exclude(user_id__in=list(following_ids))
        profiles = qs.order_by('-created_at')[:limit]
        return [CreatorProfileType.from_model(p) for p in profiles]

    @strawberry.field
    def my_followers(self, info: strawberry.types.Info, offset: int = 0, limit: int = 20) -> FollowListType:
        from ..models.follow import Follow
        user = info.context.request.user
        if not user.is_authenticated:
            return FollowListType(users=[], totalCount=0)
        qs = Follow.objects.filter(followed=user).select_related("follower", "follower__profile")
        total = qs.count()
        items = qs.order_by("-created_at")[offset:offset+limit]
        my_following_ids = set(Follow.objects.filter(follower=user).values_list("followed_id", flat=True))
        users = []
        for f in items:
            u = f.follower
            profile = getattr(u, "profile", None)
            users.append(FollowUserType(
                id=strawberry.ID(str(u.id)),
                username=u.username,
                displayName=profile.username if profile else u.username,
                avatar=profile.profile_photo_url if profile else None,
                isVerified=profile.is_verified if profile else False,
                isCreator=u.role == "creator",
                isFollowing=u.id in my_following_ids,
            ))
        return FollowListType(users=users, totalCount=total)

    @strawberry.field
    def my_following(self, info: strawberry.types.Info, offset: int = 0, limit: int = 20) -> FollowListType:
        from ..models.follow import Follow
        user = info.context.request.user
        if not user.is_authenticated:
            return FollowListType(users=[], totalCount=0)
        qs = Follow.objects.filter(follower=user).select_related("followed", "followed__profile")
        total = qs.count()
        items = qs.order_by("-created_at")[offset:offset+limit]
        users = []
        for f in items:
            u = f.followed
            profile = getattr(u, "profile", None)
            users.append(FollowUserType(
                id=strawberry.ID(str(u.id)),
                username=u.username,
                displayName=profile.username if profile else u.username,
                avatar=profile.profile_photo_url if profile else None,
                isVerified=profile.is_verified if profile else False,
                isCreator=u.role == "creator",
                isFollowing=True,
            ))
        return FollowListType(users=users, totalCount=total)

    @strawberry.field
    def is_following(self, info: strawberry.types.Info, user_id: strawberry.ID) -> bool:
        from ..models.follow import Follow
        user = info.context.request.user
        if not user.is_authenticated:
            return False
        return Follow.objects.filter(follower=user, followed_id=user_id).exists()
