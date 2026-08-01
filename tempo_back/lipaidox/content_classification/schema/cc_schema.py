import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import PlatformCategory, ContentClassification

@strawberry.type
class PlatformCategoryType:
    id: strawberry.ID
    name: str
    slug: str
    is_active: bool
    sort_order: int

    @classmethod
    def from_model(cls, instance: PlatformCategory):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            slug=instance.slug,
            is_active=instance.is_active,
            sort_order=instance.sort_order,
        )

@strawberry.type
class ContentClassificationType:
    id: strawberry.ID
    creatorId: strawberry.ID
    primaryCategory: str
    secondaryCategories: List[str]
    audienceType: str
    contentLanguage: str
    targetGender: str
    targetAgeGap: str
    targetCountry: Optional[str]
    targetInterests: List[str]
    targetProfessionalism: str
    hasImages: bool
    hasVideos: bool
    hasAudio: bool
    hasLiveStreams: bool
    hasBlog: bool
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: ContentClassification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            primaryCategory=instance.primary_category,
            secondaryCategories=instance.secondary_categories,
            audienceType=instance.audience_type,
            contentLanguage=instance.content_language,
            targetGender=instance.target_gender,
            targetAgeGap=instance.target_age_gap,
            targetCountry=instance.target_country,
            targetInterests=instance.target_interests,
            targetProfessionalism=instance.target_professionalism,
            hasImages=instance.has_images,
            hasVideos=instance.has_videos,
            hasAudio=instance.has_audio,
            hasLiveStreams=instance.has_live_streams,
            hasBlog=instance.has_blog,
            createdAt=instance.created_at,
        )

@strawberry.input
class ClassificationInput:
    primaryCategory: str
    secondaryCategories: Optional[List[str]] = None
    audienceType: Optional[str] = 'general'
    contentLanguage: Optional[str] = 'en'
    targetGender: Optional[str] = 'all'
    targetAgeGap: Optional[str] = 'all_ages'
    targetCountry: Optional[str] = None
    targetInterests: Optional[List[str]] = None
    targetProfessionalism: Optional[str] = 'all_levels'
    hasImages: Optional[bool] = False
    hasVideos: Optional[bool] = False
    hasAudio: Optional[bool] = False
    hasLiveStreams: Optional[bool] = False
    hasBlog: Optional[bool] = False
