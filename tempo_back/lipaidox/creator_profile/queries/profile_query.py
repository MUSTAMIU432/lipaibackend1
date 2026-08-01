import strawberry
from typing import List, Optional
from django.db import models
from ..models import CreatorProfile
from ..schema.profile_schema import CreatorProfileType, FollowUserType, FollowListType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class ProfileQuery:
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
