import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import CreatorProfile

@strawberry.type
class CreatorProfileType:
    id: strawberry.ID
    userId: strawberry.ID
    username: str
    usernameChangedAt: Optional[datetime]
    bio: Optional[str]
    profilePhotoUrl: Optional[str]
    coverPhotoUrl: Optional[str]
    websiteUrl: Optional[str]
    nationality: Optional[str]
    countryOfResidence: Optional[str]
    city: Optional[str]
    preferredLanguage: Optional[str]
    timezone: Optional[str]
    # Gated by `showGenderOnProfile`/`showBirthdayOnProfile` for every viewer
    # except the profile's own owner — see `from_model`'s `for_owner`.
    gender: Optional[str]
    showGenderOnProfile: bool = False
    # Month/day only ("June 10"), derived from the account's `dateOfBirth` —
    # the year never leaves the account row via this field.
    birthday: Optional[str] = None
    showBirthdayOnProfile: bool = False
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
    def from_model(cls, instance: CreatorProfile, for_owner: bool = False):
        """`for_owner=True` is for `myProfile`/`updateProfile` — the profile's
        own owner always sees their real gender/birthday regardless of the
        show-on-profile toggles, the same way a private settings screen would.
        Every other caller (`profileByUsername`, search, suggestions) leaves
        it False, so an unset toggle actually hides the value rather than
        merely hiding it in the one screen that happened to check."""
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

        gender_visible = for_owner or instance.show_gender_on_profile
        birthday_visible = for_owner or instance.show_birthday_on_profile
        dob = getattr(instance.user, "date_of_birth", None)
        birthday = dob.strftime("%B %d") if (birthday_visible and dob) else None

        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            username=instance.username,
            usernameChangedAt=instance.username_changed_at,
            bio=instance.bio,
            profilePhotoUrl=instance.profile_photo_url,
            coverPhotoUrl=instance.cover_photo_url,
            websiteUrl=instance.website_url,
            nationality=instance.nationality,
            countryOfResidence=instance.country_of_residence,
            city=instance.city,
            preferredLanguage=instance.preferred_language,
            timezone=instance.timezone,
            gender=instance.gender if gender_visible else None,
            showGenderOnProfile=instance.show_gender_on_profile,
            birthday=birthday,
            showBirthdayOnProfile=instance.show_birthday_on_profile,
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
    showGenderOnProfile: Optional[bool] = None
    showBirthdayOnProfile: Optional[bool] = None
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
