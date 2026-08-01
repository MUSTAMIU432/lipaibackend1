import strawberry
from django.db import transaction
from ..audience_utils import normalize_audience_type_string
from ..models import ContentClassification
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.cc_schema import ContentClassificationType, ClassificationInput


@strawberry.type
class ContentClassificationMutation:
    @strawberry.mutation
    def setup_classification(self, info: strawberry.types.Info, input: ClassificationInput) -> ContentClassificationType:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")

        # Must have a profile first
        try:
            profile = CreatorProfile.objects.get(user=user)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator profile must be created before classification.")

        with transaction.atomic():
            classification, created = ContentClassification.objects.update_or_create(
                creator=profile,
                defaults={
                    "primary_category": input.primaryCategory,
                    "secondary_categories": input.secondaryCategories or [],
                    "audience_type": normalize_audience_type_string(
                        input.audienceType,
                    ),
                    "content_language": input.contentLanguage or 'en',
                    "target_gender": input.targetGender or 'all',
                    "target_age_gap": input.targetAgeGap or 'all_ages',
                    "target_country": input.targetCountry,
                    "target_interests": input.targetInterests or [],
                    "target_professionalism": input.targetProfessionalism or 'all_levels',
                    "has_images": input.hasImages if input.hasImages is not None else False,
                    "has_videos": input.hasVideos if input.hasVideos is not None else False,
                    "has_audio": input.hasAudio if input.hasAudio is not None else False,
                    "has_live_streams": input.hasLiveStreams if input.hasLiveStreams is not None else False,
                    "has_blog": input.hasBlog if input.hasBlog is not None else False,
                }
            )
            
        return ContentClassificationType.from_model(classification)
