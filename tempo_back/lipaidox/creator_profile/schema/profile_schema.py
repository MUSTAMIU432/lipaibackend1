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
    socialInstagram: Optional[str]
    status: str
    isVerified: bool
    creatorTier: str
    followerCount: int
    subscriberCount: int
    totalEarnings: float
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorProfile):
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
            socialInstagram=instance.social_instagram,
            status=instance.status,
            isVerified=instance.is_verified,
            creatorTier=instance.creator_tier,
            followerCount=instance.follower_count,
            subscriberCount=instance.subscriber_count,
            totalEarnings=float(instance.total_earnings),
            createdAt=instance.created_at,
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
