import strawberry
from typing import List, Optional
from ..models import PlatformCategory, ContentClassification
from ..schema.cc_schema import PlatformCategoryType, ContentClassificationType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class ContentClassificationQuery:
    @strawberry.field
    def all_categories(self) -> List[PlatformCategoryType]:
        categories = PlatformCategory.objects.filter(is_active=True)
        return [PlatformCategoryType.from_model(c) for c in categories]

    @strawberry.field
    def my_classification(self, info: strawberry.types.Info) -> Optional[ContentClassificationType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        try:
            # Classification is linked to Profile, Profile to User
            classification = ContentClassification.objects.get(creator__user=user)
            return ContentClassificationType.from_model(classification)
        except ContentClassification.DoesNotExist:
            return None

    @strawberry.field
    def creators_by_category(self, slug: str) -> List[ContentClassificationType]:
        classifications = ContentClassification.objects.filter(primary_category=slug)
        return [ContentClassificationType.from_model(c) for c in classifications]
