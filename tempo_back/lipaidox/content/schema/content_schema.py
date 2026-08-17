import strawberry
from strawberry.scalars import JSON
from typing import Optional, List, Annotated
from datetime import datetime

from lipaidox.creator_profile.schema.profile_schema import CreatorProfileType

from ..models import Content, ContentSeries, ContentMedia, ContentAttachment, ContentAccessRule, ContentTag


@strawberry.type
class TrimVideoResult:
    """Returned by trimContentVideo mutation."""
    mediaId: strawberry.ID
    fileUrl: str
    durationSeconds: Optional[float]
    fileSizeBytes: Optional[int]


@strawberry.input
class TrimVideoInput:
    contentId: strawberry.ID
    mediaId: strawberry.ID
    startTime: float   # seconds
    endTime: float     # seconds

@strawberry.type
class ContentSeriesType:
    id: strawberry.ID
    title: str
    description: Optional[str]
    thumbnailUrl: Optional[str]
    episodeCount: int
    isComplete: bool
    sortOrder: int
    seriesType: str
    createdAt: datetime
    updatedAt: datetime

    @strawberry.field
    def parent(self) -> Optional["ContentSeriesType"]:
        from ..models import ContentSeries
        instance = ContentSeries.objects.filter(id=self.id).first()
        if instance and instance.parent:
            return ContentSeriesType.from_model(instance.parent)
        return None

    @strawberry.field
    def subSeries(self) -> List["ContentSeriesType"]:
        from ..models import ContentSeries
        items = ContentSeries.objects.filter(parent_id=self.id).order_by('sort_order', 'created_at')
        return [ContentSeriesType.from_model(s) for s in items]

    @strawberry.field
    def episodes(self) -> List[Annotated["ContentType", strawberry.lazy(".content_schema")]]:
        from ..models import Content
        items = Content.objects.filter(series_id=self.id).order_by('episode_number', 'created_at')
        return [ContentType.from_model(c) for c in items]

    @classmethod
    def from_model(cls, instance: ContentSeries):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            description=instance.description,
            thumbnailUrl=instance.thumbnail_url,
            episodeCount=instance.episode_count,
            isComplete=instance.is_complete,
            sortOrder=instance.sort_order,
            seriesType=instance.series_type,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )

@strawberry.type
class MediaRenditionType:
    quality: str
    url: str


@strawberry.type
class MediaCaptionType:
    lang: str
    label: str
    url: str


def _renditions(instance) -> "List[MediaRenditionType]":
    out = []
    for r in (getattr(instance, "renditions", None) or []):
        if isinstance(r, dict) and r.get("url"):
            out.append(MediaRenditionType(quality=str(r.get("quality") or "Auto"), url=str(r["url"])))
    return out


def _captions(instance) -> "List[MediaCaptionType]":
    out = []
    for c in (getattr(instance, "captions", None) or []):
        if isinstance(c, dict) and c.get("url"):
            out.append(MediaCaptionType(
                lang=str(c.get("lang") or "en"),
                label=str(c.get("label") or c.get("lang") or "Caption"),
                url=str(c["url"]),
            ))
    return out


@strawberry.type
class ContentMediaType:
    id: strawberry.ID
    mediaType: str
    mediaRole: str
    # Nullable so the read path can withhold the URL for paid content the viewer
    # hasn't unlocked (thumbnailUrl is kept for the blurred preview).
    fileUrl: Optional[str]
    fileName: Optional[str]
    fileSizeBytes: Optional[int]
    durationSeconds: Optional[int]
    thumbnailUrl: Optional[str]
    sortOrder: int
    slideTopic: Optional[str]
    slideHint: Optional[str]
    isPreviewSlide: bool
    renditions: List[MediaRenditionType]
    captions: List[MediaCaptionType]

    @classmethod
    def from_model(cls, instance: ContentMedia):
        return cls(
            id=strawberry.ID(str(instance.id)),
            mediaType=instance.media_type,
            mediaRole=instance.media_role,
            fileUrl=instance.file_url,
            fileName=instance.file_name,
            fileSizeBytes=instance.file_size_bytes,
            durationSeconds=instance.duration_seconds,
            thumbnailUrl=getattr(instance, 'thumbnail_url', None),
            sortOrder=instance.sort_order,
            slideTopic=instance.slide_topic,
            slideHint=instance.slide_hint,
            isPreviewSlide=instance.is_preview_slide,
            renditions=_renditions(instance),
            captions=_captions(instance),
        )

@strawberry.type
class ContentAttachmentType:
    id: strawberry.ID
    attachmentType: str
    fileUrl: str
    fileName: str
    title: Optional[str]
    description: Optional[str]
    fileSizeBytes: Optional[int]
    thumbnailUrl: Optional[str]
    downloadCount: int
    createdAt: datetime
    renditions: List[MediaRenditionType]
    captions: List[MediaCaptionType]

    @classmethod
    def from_model(cls, instance: ContentAttachment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            attachmentType=instance.attachment_type,
            fileUrl=instance.file_url,
            fileName=instance.file_name,
            title=getattr(instance, 'title', None),
            description=getattr(instance, 'description', None),
            fileSizeBytes=instance.file_size_bytes,
            thumbnailUrl=getattr(instance, 'thumbnail_url', None),
            downloadCount=instance.download_count,
            createdAt=instance.created_at,
            renditions=_renditions(instance),
            captions=_captions(instance),
        )

@strawberry.type
class ContentAccessRuleType:
    id: strawberry.ID
    subscriberOnlyPreview: bool
    geoRestrictions: List[str]
    previewDurationSeconds: Optional[int]
    previewSlideCount: Optional[int]
    allowDownload: bool
    expiresAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: ContentAccessRule):
        return cls(
            id=strawberry.ID(str(instance.id)),
            subscriberOnlyPreview=instance.subscriber_only_preview,
            geoRestrictions=instance.geo_restrictions,
            previewDurationSeconds=instance.preview_duration_seconds,
            previewSlideCount=instance.preview_slide_count,
            allowDownload=instance.allow_download,
            expiresAt=instance.expires_at,
        )

@strawberry.type
class ContentTagType:
    id: strawberry.ID
    tag: str

    @classmethod
    def from_model(cls, instance: ContentTag):
        return cls(
            id=strawberry.ID(str(instance.id)),
            tag=instance.tag,
        )

@strawberry.type
class ContentType:
    id: strawberry.ID
    title: str
    description: Optional[str]
    contentFormat: str
    style: Optional[JSON]
    status: str
    accessType: str
    oneTimePrice: Optional[float]
    timedPrice: Optional[float]
    timedDurationValue: Optional[int]
    timedDurationUnit: Optional[str]
    categories: List[str]
    allowDownload: bool
    isContinuous: bool
    episodeNumber: Optional[int]
    viewCount: int
    likeCount: int
    publishedAt: Optional[datetime]
    scheduledAt: Optional[datetime]
    attachments: List[ContentAttachmentType]
    tags: List[str]
    series: Optional[ContentSeriesType]
    accessRules: Optional[ContentAccessRuleType]
    primaryCategory: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    @strawberry.field
    def creator_profile(self) -> Optional[CreatorProfileType]:
        """Public creator row for feed cards (resolved per content id)."""
        try:
            row = Content.objects.select_related("creator").get(pk=str(self.id))
        except Content.DoesNotExist:
            return None
        return CreatorProfileType.from_model(row.creator)

    @strawberry.field
    def average_rating(self) -> float:
        from django.db.models import Avg
        from ..models import ContentReview, ContentReviewStatus
        avg = ContentReview.objects.filter(
            content_id=str(self.id), status=ContentReviewStatus.PUBLISHED, deleted_at__isnull=True
        ).aggregate(a=Avg("rating"))["a"]
        return round(float(avg or 0.0), 2)

    @strawberry.field
    def review_count(self) -> int:
        from ..models import ContentReview, ContentReviewStatus
        return ContentReview.objects.filter(
            content_id=str(self.id), status=ContentReviewStatus.PUBLISHED, deleted_at__isnull=True
        ).count()

    @strawberry.field
    def comment_count(self) -> int:
        from ..models import ContentComment, ContentCommentStatus
        return ContentComment.objects.filter(
            content_id=str(self.id), status=ContentCommentStatus.PUBLISHED, deleted_at__isnull=True
        ).count()

    def _content_row(self) -> Optional[Content]:
        try:
            return Content.objects.select_related("creator").get(pk=str(self.id))
        except Content.DoesNotExist:
            return None

    @strawberry.field
    def media(self, info: strawberry.types.Info) -> List[ContentMediaType]:
        """Media rows, with paid asset URLs withheld from viewers without access.
        The thumbnail role and thumbnailUrl are always returned for the preview."""
        from ..access import viewer_has_access
        content = self._content_row()
        if content is None:
            return []
        user = getattr(info.context.request, "user", None)
        allowed = viewer_has_access(user, content)
        out: List[ContentMediaType] = []
        for m in content.media.all().order_by("sort_order"):
            mt = ContentMediaType.from_model(m)
            if not allowed and (m.media_role or "").lower() != "thumbnail":
                mt.fileUrl = None
            out.append(mt)
        return out

    @strawberry.field
    def viewer_has_access(self, info: strawberry.types.Info) -> bool:
        """Whether the current viewer may see the full content (owner/free/paid/subbed)."""
        from ..access import viewer_has_access as _vha
        content = self._content_row()
        if content is None:
            return False
        return _vha(getattr(info.context.request, "user", None), content)

    @strawberry.field
    def is_liked_by_viewer(self, info: strawberry.types.Info) -> bool:
        """Whether the current viewer has liked this content."""
        content = self._content_row()
        user = getattr(info.context.request, "user", None)
        if content is None or not getattr(user, "is_authenticated", False):
            return False
        from ..models import ContentLike
        return ContentLike.objects.filter(user=user, content=content).exists()

    @strawberry.field
    def is_saved_by_viewer(self, info: strawberry.types.Info) -> bool:
        """Whether the current viewer has saved/bookmarked this content."""
        content = self._content_row()
        user = getattr(info.context.request, "user", None)
        if content is None or not getattr(user, "is_authenticated", False):
            return False
        from ..models import ContentBookmark
        return ContentBookmark.objects.filter(user=user, content=content).exists()

    @strawberry.field
    def is_purchased(self, info: strawberry.types.Info) -> bool:
        """Whether the current viewer has an active PPV purchase for this content."""
        from ..access import viewer_purchase
        content = self._content_row()
        if content is None:
            return False
        purchase = viewer_purchase(getattr(info.context.request, "user", None), content)
        return bool(purchase and purchase.has_access)

    @strawberry.field
    def purchase_expires_at(self, info: strawberry.types.Info) -> Optional[datetime]:
        """Expiry of the viewer's timed PPV access, if any."""
        from ..access import viewer_purchase
        content = self._content_row()
        if content is None:
            return None
        purchase = viewer_purchase(getattr(info.context.request, "user", None), content)
        return purchase.expires_at if purchase else None

    @classmethod
    def from_model(cls, instance: Content):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            description=instance.description,
            contentFormat=instance.content_format,
            style=instance.style,
            status=instance.status,
            accessType=instance.access_type,
            oneTimePrice=float(instance.one_time_price) if instance.one_time_price else None,
            timedPrice=float(instance.timed_price) if instance.timed_price else None,
            timedDurationValue=instance.timed_duration_value,
            timedDurationUnit=instance.timed_duration_unit,
            categories=instance.categories,
            allowDownload=instance.allow_download,
            isContinuous=instance.is_continuous,
            episodeNumber=instance.episode_number,
            viewCount=instance.view_count,
            likeCount=instance.like_count,
            publishedAt=instance.published_at,
            scheduledAt=instance.scheduled_at,
            attachments=[ContentAttachmentType.from_model(a) for a in instance.attachments.all()],
            tags=[t.tag for t in instance.tags_list.all()],
            series=ContentSeriesType.from_model(instance.series) if instance.series else None,
            accessRules=ContentAccessRuleType.from_model(instance.access_rules) if hasattr(instance, 'access_rules') else None,
            primaryCategory=instance.primary_category,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )

@strawberry.input
class NewSeriesInput:
    title: str
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    parentId: Optional[strawberry.ID] = None
    sortOrder: int = 0
    seriesType: str = "collection"

@strawberry.input
class UpdateContentSeriesInput:
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    isComplete: Optional[bool] = None
    parentId: Optional[strawberry.ID] = None
    sortOrder: Optional[int] = None
    seriesType: Optional[str] = None

@strawberry.input
class MediaInput:
    mediaType: str
    mediaRole: str = "main" # main, thumbnail, slideshow_image
    fileUrl: str
    fileName: Optional[str] = None
    sortOrder: int = 0
    slideTopic: Optional[str] = None
    slideHint: Optional[str] = None
    isPreviewSlide: bool = False

@strawberry.input
class UpdateMediaInput:
    fileUrl: Optional[str] = None
    fileName: Optional[str] = None
    sortOrder: Optional[int] = None
    slideTopic: Optional[str] = None
    slideHint: Optional[str] = None
    isPreviewSlide: Optional[bool] = None

@strawberry.input
class SlideUploadInput:
    fileUrl: str
    title: str
    hint: Optional[str] = None
    isPreview: bool = False
    sortOrder: int = 0

@strawberry.input
class AttachmentInput:
    attachmentType: str
    fileUrl: str
    fileName: str
    title: Optional[str] = None
    description: Optional[str] = None
    fileSizeBytes: Optional[int] = None
    thumbnailUrl: Optional[str] = None

@strawberry.input
class AccessRuleInput:
    subscriberOnlyPreview: Optional[bool] = None
    geoRestrictions: Optional[List[str]] = None
    previewDurationSeconds: Optional[int] = None
    previewSlideCount: Optional[int] = None
    allowDownload: Optional[bool] = None
    expiresAt: Optional[datetime] = None

@strawberry.input
class UpdateContentInput:
    title: Optional[str] = None
    description: Optional[str] = None
    contentFormat: Optional[str] = None
    style: Optional[JSON] = None
    status: Optional[str] = None
    categories: Optional[List[str]] = None
    primaryCategory: Optional[str] = None
    tags: Optional[List[str]] = None
    
    # Access
    accessType: Optional[str] = None
    oneTimePrice: Optional[float] = None
    timedPrice: Optional[float] = None
    timedDurationValue: Optional[int] = None
    timedDurationUnit: Optional[str] = None
    allowDownload: Optional[bool] = None
    
    # Series
    isContinuous: Optional[bool] = None
    seriesId: Optional[strawberry.ID] = None
    episodeNumber: Optional[int] = None

    # Scheduling
    scheduledAt: Optional[datetime] = None
    
    # Detailed Access Rules
    accessRule: Optional[AccessRuleInput] = None

@strawberry.input
class CreateContentInput:
    title: str
    description: Optional[str] = None
    contentFormat: str = "single_image"
    style: Optional[JSON] = None
    status: Optional[str] = "draft"
    categories: List[str] = strawberry.field(default_factory=list)
    primaryCategory: Optional[str] = None
    tags: Optional[List[str]] = None
    
    # Access
    accessType: str = "free"
    oneTimePrice: Optional[float] = None
    timedPrice: Optional[float] = None
    timedDurationValue: Optional[int] = None
    timedDurationUnit: Optional[str] = None
    allowDownload: bool = False
    
    # Series
    isContinuous: bool = False
    seriesId: Optional[strawberry.ID] = None
    newSeries: Optional[NewSeriesInput] = None
    episodeNumber: Optional[int] = None

    # Scheduling
    scheduledAt: Optional[datetime] = None
    
    # Detailed Access Rules
    accessRule: Optional[AccessRuleInput] = None