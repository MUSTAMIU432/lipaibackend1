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
    socialTwitter: Optional[str]
    socialTiktok: Optional[str]
    socialYoutube: Optional[str]
    status: str
    isVerified: bool
    creatorTier: str
    followerCount: int
    followingCount: int
    subscriberCount: int
    contentCount: int
    totalEarnings: float
    createdAt: datetime
    # Public subscription price so a viewer's profile can show what it costs to
    # subscribe (and unlock the creator's exclusive content). Null = the creator
    # hasn't priced/enabled subscriptions.
    subscriptionPrice: Optional[float] = None
    subscriptionEnabled: bool = False
    # Set on the "Switch to Creator" wizard's Business path; a plain Creator
    # account leaves everything below unset.
    accountKind: str = "creator"
    businessCategory: Optional[str] = None
    showCategoryOnProfile: bool = True
    businessName: Optional[str] = None
    businessEmail: Optional[str] = None
    businessPhone: Optional[str] = None
    businessAddress: Optional[str] = None
    businessWebsite: Optional[str] = None
    contactShowEmail: bool = True
    contactShowPhone: bool = True
    contactShowWhatsapp: bool = True
    contactShowDirections: bool = False

    @classmethod
    def from_model(cls, instance: CreatorProfile):
        # Local imports: `Content` lives in the `content` app, which itself
        # references `creator_profile` via a string FK — a top-level import
        # here would risk a circular import between the two apps.
        from lipaidox.content.models.content import Content, ContentStatus

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
            socialTwitter=instance.social_twitter,
            socialTiktok=instance.social_tiktok,
            socialYoutube=instance.social_youtube,
            status=instance.status,
            isVerified=instance.is_verified,
            creatorTier=instance.creator_tier,
            followerCount=instance.follower_count,
            followingCount=instance.user.following_set.count(),
            subscriberCount=instance.subscriber_count,
            contentCount=Content.objects.filter(
                creator=instance, status=ContentStatus.PUBLISHED
            ).count(),
            totalEarnings=float(instance.total_earnings),
            createdAt=instance.created_at,
            subscriptionPrice=sub_price,
            subscriptionEnabled=sub_enabled,
            accountKind=instance.account_kind,
            businessCategory=instance.business_category,
            showCategoryOnProfile=instance.show_category_on_profile,
            businessName=instance.business_name,
            businessEmail=instance.business_email,
            businessPhone=instance.business_phone,
            businessAddress=instance.business_address,
            businessWebsite=instance.business_website,
            contactShowEmail=instance.contact_show_email,
            contactShowPhone=instance.contact_show_phone,
            contactShowWhatsapp=instance.contact_show_whatsapp,
            contactShowDirections=instance.contact_show_directions,
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
    socialTwitter: Optional[str] = None
    socialTiktok: Optional[str] = None
    socialYoutube: Optional[str] = None

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
