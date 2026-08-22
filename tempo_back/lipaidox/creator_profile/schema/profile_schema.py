import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import CreatorProfile

@strawberry.type
class CreatorProfileType:
    id: strawberry.ID
    userId: strawberry.ID
    username: str
    bio: Optional[str]
    profilePhotoUrl: Optional[str]
    coverPhotoUrl: Optional[str]
    websiteUrl: Optional[str]
    nationality: Optional[str]
    countryOfResidence: Optional[str]
    city: Optional[str]
    preferredLanguage: Optional[str]
    timezone: Optional[str]
    gender: Optional[str]
    areaOfInterest: Optional[str]
    contentCategories: List[str]
    socialInstagram: Optional[str]
    status: str
    isVerified: bool
    creatorTier: str
    followerCount: int
    subscriberCount: int
    totalEarnings: float
    createdAt: datetime
    # Public subscription price so a viewer's profile can show what it costs to
    # subscribe (and unlock the creator's exclusive content). Null = the creator
    # hasn't priced/enabled subscriptions.
    subscriptionPrice: Optional[float] = None
    subscriptionEnabled: bool = False

    @classmethod
    def from_model(cls, instance: CreatorProfile):
        sub_price = None
        sub_enabled = False
        settings = getattr(instance, "monetization_settings", None)
        if settings is not None:
            sub_enabled = bool(getattr(settings, "subscription_enabled", False))
            raw = getattr(settings, "subscription_price", None)
            if raw is not None:
                sub_price = float(raw)
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            username=instance.username,
            bio=instance.bio,
            profilePhotoUrl=instance.profile_photo_url,
            coverPhotoUrl=instance.cover_photo_url,
            websiteUrl=instance.website_url,
            nationality=instance.nationality,
            countryOfResidence=instance.country_of_residence,
            city=instance.city,
            preferredLanguage=instance.preferred_language,
            timezone=instance.timezone,
            gender=instance.gender,
            areaOfInterest=instance.area_of_interest,
            contentCategories=list(instance.content_categories or []),
            socialInstagram=instance.social_instagram,
            status=instance.status,
            isVerified=instance.is_verified,
            creatorTier=instance.creator_tier,
            followerCount=instance.follower_count,
            subscriberCount=instance.subscriber_count,
            totalEarnings=float(instance.total_earnings),
            createdAt=instance.created_at,
            subscriptionPrice=sub_price,
            subscriptionEnabled=sub_enabled,
        )

@strawberry.input
class CreateProfileInput:
    username: str
    bio: Optional[str] = None

@strawberry.input
class UpdateProfileInput:
    username: Optional[str] = None
    bio: Optional[str] = None
    profilePhotoUrl: Optional[str] = None
    coverPhotoUrl: Optional[str] = None
    websiteUrl: Optional[str] = None
    countryOfResidence: Optional[str] = None
    city: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    areaOfInterest: Optional[str] = None
    contentCategories: Optional[List[str]] = None
    preferredLanguage: Optional[str] = None
    timezone: Optional[str] = None
    socialInstagram: Optional[str] = None

@strawberry.type
class FollowUserType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool
    isCreator: bool
    isFollowing: bool

@strawberry.type
class FollowListType:
    users: list[FollowUserType]
    totalCount: int
