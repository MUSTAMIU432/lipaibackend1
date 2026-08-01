import strawberry
from typing import List, Optional
from ..models import Content, ContentSeries, ContentTag
from ..schema.content_schema import ContentType, ContentSeriesType, ContentTagType
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator

@strawberry.type
class ContentQuery:
    @strawberry.field
    @require_creator
    def my_content(self, info: strawberry.types.Info) -> List[ContentType]:
        user = info.context.request.user
        content_items = Content.objects.filter(creator__user=user).select_related('series', 'access_rules').order_by('-created_at')
        return [ContentType.from_model(c) for c in content_items]

    @strawberry.field
    @require_creator
    def my_drafts(self, info: strawberry.types.Info) -> List[ContentType]:
        """Return all content with status draft or scheduled, newest first."""
        user = info.context.request.user
        items = (
            Content.objects
            .filter(creator__user=user, status__in=['draft', 'scheduled'])
            .select_related('series', 'access_rules')
            .prefetch_related('media')
            .order_by('-updated_at')
        )
        return [ContentType.from_model(c) for c in items]

    @strawberry.field
    @require_creator
    def my_series(self, info: strawberry.types.Info) -> List[ContentSeriesType]:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        series_items = ContentSeries.objects.filter(creator__user=user)
        return [ContentSeriesType.from_model(s) for s in series_items]

    @strawberry.field
    @require_creator
    def my_root_series(self, info: strawberry.types.Info) -> List[ContentSeriesType]:
        """Fetch only top-level series for the current creator."""
        user = info.context.request.user
        series_items = ContentSeries.objects.filter(creator__user=user, parent=None)
        return [ContentSeriesType.from_model(s) for s in series_items]

    @strawberry.field
    def series_episodes(self, series_id: strawberry.ID) -> List[ContentType]:
        episodes = Content.objects.filter(series_id=series_id).order_by('episode_number', 'created_at')
        return [ContentType.from_model(c) for c in episodes]

    @strawberry.field
    def content_by_id(self, id: strawberry.ID) -> Optional[ContentType]:
        try:
            content = (
                Content.objects.select_related('creator')
                .prefetch_related('media', 'attachments', 'tags_list', 'series')
                .get(id=id)
            )
            return ContentType.from_model(content)
        except Content.DoesNotExist:
            return None

    @strawberry.field
    def series_by_id(self, id: strawberry.ID) -> Optional[ContentSeriesType]:
        try:
            series = ContentSeries.objects.get(id=id)
            return ContentSeriesType.from_model(series)
        except ContentSeries.DoesNotExist:
            return None

    @strawberry.field
    def all_public_content(self, info: strawberry.types.Info, category: Optional[str] = None) -> List[ContentType]:
        tenant = get_current_tenant()
        queryset = (
            Content.objects.filter(tenant=tenant, status='published')
            .select_related('creator')
            .prefetch_related('media')
            .order_by('-published_at')
        )
        if category:
            queryset = queryset.filter(categories__contains=[category])
        return [ContentType.from_model(c) for c in queryset]

    @strawberry.field
    def all_public_series(self, info: strawberry.types.Info) -> List[ContentSeriesType]:
        tenant = get_current_tenant()
        queryset = ContentSeries.objects.filter(tenant=tenant).order_by('-created_at')
        return [ContentSeriesType.from_model(s) for s in queryset]

    @strawberry.field
    def all_public_root_series(self, info: strawberry.types.Info) -> List[ContentSeriesType]:
        """Fetch only top-level public series (Collections/Courses)."""
        tenant = get_current_tenant()
        queryset = ContentSeries.objects.filter(tenant=tenant, parent=None).order_by('-created_at')
        return [ContentSeriesType.from_model(s) for s in queryset]

    @strawberry.field
    def search_tags(self, query: str) -> List[str]:
        # Return unique tags matching query
        tags = ContentTag.objects.filter(tag__icontains=query).values_list('tag', flat=True).distinct()[:10]
        return list(tags)

    @strawberry.field
    def single_content(self, id: strawberry.ID) -> Optional[ContentType]:
        """
        Fetch a single content item with all its details.
        """
        return self.content_by_id(id)

    @strawberry.field
    def full_series_content(self, series_id: strawberry.ID) -> Optional[ContentSeriesType]:
        """
        Fetch a series with all its episodes and metadata.
        """
        return self.series_by_id(series_id)