import logging

import strawberry
from typing import List, Optional
from django.db import transaction
from ..models import (
    Content, ContentMedia, ContentSeries, 
    ContentAttachment, ContentAccessRule, ContentTag
)
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.content_schema import (
    ContentType, CreateContentInput, MediaInput, SlideUploadInput, UpdateMediaInput,
    ContentSeriesType, AttachmentInput, ContentAccessRuleType, AccessRuleInput,
    ContentMediaType, ContentAttachmentType, UpdateContentInput,
    UpdateContentSeriesInput, NewSeriesInput, TrimVideoResult, TrimVideoInput
)
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator, require_creator_or_admin

logger = logging.getLogger(__name__)


def _announce_if_published(content) -> None:
    """Fan out a NEW_CONTENT_POSTED notification the first time content is published.

    Idempotent and best-effort: the service guards on ``followers_notified`` and
    swallows its own errors, so this can be called from every publish path
    without risk of double-blasting or breaking the mutation.
    """
    try:
        from lipaidox.notifications.services.content_notifications import notify_new_content_posted
        notify_new_content_posted(content)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("new-content fan-out skipped: %s", exc)


def _schedule_main_video_processing(media_obj_id: int, user_id: int) -> None:
    """Enqueue Celery pipeline for main video; fall back to sync if broker is unavailable."""
    try:
        from django.contrib.contenttypes.models import ContentType

        from lipaidox.media_processor.tasks import process_media_pipeline_task

        ct = ContentType.objects.get_for_model(ContentMedia)
        try:
            process_media_pipeline_task.delay(ct.id, media_obj_id, user_id)
        except Exception:
            logger.debug(
                "media pipeline: async enqueue failed, running sync (ct_id=%s media_id=%s)",
                ct.id,
                media_obj_id,
                exc_info=True,
            )
            process_media_pipeline_task(ct.id, media_obj_id, user_id)
    except ImportError:
        logger.warning(
            "lipaidox.media_processor.tasks missing; skipping video pipeline for media_id=%s",
            media_obj_id,
        )


@strawberry.type
class ContentMutation:
    @strawberry.mutation
    @require_creator
    def create_content(
        self, 
        info: strawberry.types.Info, 
        input: CreateContentInput, 
        media: List[MediaInput],
        attachments: Optional[List[AttachmentInput]] = None
    ) -> ContentType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()

        with transaction.atomic():
            # 1. Handle Series
            final_series_id = input.seriesId
            if input.isContinuous and input.newSeries:
                new_series = ContentSeries.objects.create(
                    creator=profile,
                    tenant=tenant,
                    title=input.newSeries.title,
                    description=input.newSeries.description
                )
                final_series_id = new_series.id

            # 2. Create Content
            from django.utils import timezone as dj_timezone

            _status = input.status or "draft"
            _published_at = (
                dj_timezone.now() if _status == "published" else None
            )
            content = Content.objects.create(
                creator=profile,
                tenant=tenant,
                title=input.title,
                description=input.description,
                content_format=input.contentFormat,
                style=input.style,
                status=_status,
                published_at=_published_at,
                categories=input.categories,
                primary_category=input.primaryCategory,
                access_type=input.accessType,
                one_time_price=input.oneTimePrice,
                timed_price=input.timedPrice,
                timed_duration_value=input.timedDurationValue,
                timed_duration_unit=input.timedDurationUnit,
                allow_download=input.allowDownload,
                is_continuous=input.isContinuous,
                episode_number=input.episodeNumber,
                series_id=final_series_id,
                scheduled_at=input.scheduledAt
            )

            # 2b. Handle Tags
            if input.tags:
                for t in input.tags:
                    ContentTag.objects.get_or_create(content=content, tag=t.strip().lower())

            # 3. Handle Media with Roles
            for m in media:
                media_obj = ContentMedia.objects.create(
                    content=content,
                    media_type=m.mediaType,
                    media_role=m.mediaRole,
                    file_url=m.fileUrl,
                    file_name=m.fileName,
                    sort_order=m.sortOrder,
                    slide_topic=m.slideTopic,
                    slide_hint=m.slideHint,
                    is_preview_slide=m.isPreviewSlide
                )
                
                # Trigger Processing if Video
                if m.mediaType == 'video' and m.mediaRole == 'main':
                    _schedule_main_video_processing(media_obj.id, user.id)
            
            # 4. Handle Attachments
            if attachments:
                for a in attachments:
                    ContentAttachment.objects.create(
                        content=content,
                        attachment_type=a.attachmentType,
                        file_url=a.fileUrl,
                        file_name=a.fileName,
                        title=getattr(a, 'title', None),
                        description=getattr(a, 'description', None),
                        file_size_bytes=a.fileSizeBytes,
                        thumbnail_url=getattr(a, 'thumbnailUrl', None),
                    )
            
            # 5. Initialize Access Rules
            rule_data = {
                "content": content,
                "allow_download": input.allowDownload
            }
            if input.accessRule:
                if input.accessRule.subscriberOnlyPreview is not None: rule_data["subscriber_only_preview"] = input.accessRule.subscriberOnlyPreview
                if input.accessRule.geoRestrictions is not None: rule_data["geo_restrictions"] = input.accessRule.geoRestrictions
                if input.accessRule.previewDurationSeconds is not None: rule_data["preview_duration_seconds"] = input.accessRule.previewDurationSeconds
                if input.accessRule.previewSlideCount is not None: rule_data["preview_slide_count"] = input.accessRule.previewSlideCount
                if input.accessRule.allowDownload is not None: rule_data["allow_download"] = input.accessRule.allowDownload
                if input.accessRule.expiresAt is not None: rule_data["expires_at"] = input.accessRule.expiresAt
            
            ContentAccessRule.objects.create(**rule_data)

        _announce_if_published(content)
        return ContentType.from_model(content)

    @strawberry.mutation
    @require_creator
    def update_content(self, info: strawberry.types.Info, id: strawberry.ID, input: UpdateContentInput) -> ContentType:
        content = Content.objects.get(id=id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only update your own content")

        with transaction.atomic():
            if input.title is not None: content.title = input.title
            if input.description is not None: content.description = input.description
            if input.contentFormat is not None: content.content_format = input.contentFormat
            if input.style is not None: content.style = input.style
            if input.status is not None: 
                content.status = input.status
                if input.status == 'published' and not content.published_at:
                    from django.utils import timezone
                    content.published_at = timezone.now()
            if input.categories is not None: content.categories = input.categories
            if input.primaryCategory is not None: content.primary_category = input.primaryCategory
            if input.accessType is not None: content.access_type = input.accessType
            if input.oneTimePrice is not None: content.one_time_price = input.oneTimePrice
            if input.timedPrice is not None: content.timed_price = input.timedPrice
            if input.timedDurationValue is not None: content.timed_duration_value = input.timedDurationValue
            if input.timedDurationUnit is not None: content.timed_duration_unit = input.timedDurationUnit
            if input.allowDownload is not None: content.allow_download = input.allowDownload
            if input.isContinuous is not None: content.is_continuous = input.isContinuous
            if input.episodeNumber is not None: content.episode_number = input.episodeNumber
            if input.seriesId is not None: content.series_id = input.seriesId
            if input.scheduledAt is not None: content.scheduled_at = input.scheduledAt

            content.save()

            # Handle Tags
            if input.tags is not None:
                # Remove old tags, add new ones
                content.tags_list.all().delete()
                for t in input.tags:
                    ContentTag.objects.get_or_create(content=content, tag=t.strip().lower())

            # Handle Access Rules
            if input.accessRule:
                rule, created = ContentAccessRule.objects.get_or_create(content=content)
                if input.accessRule.subscriberOnlyPreview is not None: rule.subscriber_only_preview = input.accessRule.subscriberOnlyPreview
                if input.accessRule.geoRestrictions is not None: rule.geo_restrictions = input.accessRule.geoRestrictions
                if input.accessRule.previewDurationSeconds is not None: rule.preview_duration_seconds = input.accessRule.previewDurationSeconds
                if input.accessRule.previewSlideCount is not None: rule.preview_slide_count = input.accessRule.previewSlideCount
                if input.accessRule.allowDownload is not None: rule.allow_download = input.accessRule.allowDownload
                if input.accessRule.expiresAt is not None: rule.expires_at = input.accessRule.expiresAt
                rule.save()

        _announce_if_published(content)
        return ContentType.from_model(content)

    @strawberry.mutation
    @require_creator_or_admin
    def update_content_status(self, info: strawberry.types.Info, id: strawberry.ID, status: str) -> ContentType:
        content = Content.objects.get(id=id)
        # Additional ownership check for creators
        user = info.context.request.user
        if user.role == 'creator' and content.creator.user != user:
            raise Exception("You can only update your own content")
        content.status = status
        if status == 'published' and not content.published_at:
            from django.utils import timezone
            content.published_at = timezone.now()
        content.save()
        _announce_if_published(content)
        return ContentType.from_model(content)

    @strawberry.mutation
    @require_creator_or_admin
    def delete_content(self, info: strawberry.types.Info, id: strawberry.ID) -> bool:
        content = Content.objects.get(id=id)
        # Additional ownership check for creators
        user = info.context.request.user
        if user.role == 'creator' and content.creator.user != user:
            raise Exception("You can only delete your own content")
        Content.objects.get(id=id).delete()
        return True

    @strawberry.mutation
    @require_creator
    def create_or_update_access_rules(self, info: strawberry.types.Info, content_id: strawberry.ID, input: AccessRuleInput) -> ContentAccessRuleType:
        # Verify ownership
        content = Content.objects.get(id=content_id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only manage access rules for your own content")
        rule, created = ContentAccessRule.objects.get_or_create(content_id=content_id)
        if input.subscriberOnlyPreview is not None: rule.subscriber_only_preview = input.subscriberOnlyPreview
        if input.geoRestrictions is not None: rule.geo_restrictions = input.geoRestrictions
        if input.previewDurationSeconds is not None: rule.preview_duration_seconds = input.previewDurationSeconds
        if input.previewSlideCount is not None: rule.preview_slide_count = input.previewSlideCount
        if input.allowDownload is not None: rule.allow_download = input.allowDownload
        if input.expiresAt is not None: rule.expires_at = input.expiresAt
        rule.save()
        return ContentAccessRuleType.from_model(rule)

    @strawberry.mutation
    @require_creator
    def create_series(self, info: strawberry.types.Info, input: NewSeriesInput) -> ContentSeriesType:
        user = info.context.request.user
        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()
        series = ContentSeries.objects.create(
            creator=profile, 
            tenant=tenant, 
            title=input.title, 
            description=input.description,
            thumbnail_url=input.thumbnailUrl,
            parent_id=input.parentId,
            sort_order=input.sortOrder,
            series_type=input.seriesType
        )
        return ContentSeriesType.from_model(series)

    @strawberry.mutation
    @require_creator
    def update_series(self, info: strawberry.types.Info, id: strawberry.ID, input: UpdateContentSeriesInput) -> ContentSeriesType:
        series = ContentSeries.objects.get(id=id)
        user = info.context.request.user
        if series.creator.user != user:
            raise Exception("You can only update your own series")
        
        if input.title is not None: series.title = input.title
        if input.description is not None: series.description = input.description
        if input.thumbnailUrl is not None: series.thumbnail_url = input.thumbnailUrl
        if input.isComplete is not None: series.is_complete = input.isComplete
        if input.parentId is not None: series.parent_id = input.parentId
        if input.sortOrder is not None: series.sort_order = input.sortOrder
        if input.seriesType is not None: series.series_type = input.seriesType
        
        series.save()
        return ContentSeriesType.from_model(series)

    @strawberry.mutation
    @require_creator
    def delete_series(self, info: strawberry.types.Info, id: strawberry.ID) -> bool:
        series = ContentSeries.objects.get(id=id)
        user = info.context.request.user
        if series.creator.user != user:
            raise Exception("You can only delete your own series")
        series.delete()
        return True

    @strawberry.mutation
    @require_creator
    def add_content_media(self, info: strawberry.types.Info, content_id: strawberry.ID, input: MediaInput) -> ContentMediaType:
        # Verify ownership
        content = Content.objects.get(id=content_id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only add media to your own content")
        media = ContentMedia.objects.create(
            content_id=content_id, media_type=input.mediaType, media_role=input.mediaRole,
            file_url=input.fileUrl, file_name=input.fileName, sort_order=input.sortOrder,
            slide_topic=input.slideTopic, slide_hint=input.slideHint, is_preview_slide=input.isPreviewSlide
        )
        
        # Trigger Processing if Video
        if input.mediaType == 'video' and input.mediaRole == 'main':
            _schedule_main_video_processing(media.id, user.id)
            
        return ContentMediaType.from_model(media)

    @strawberry.mutation
    @require_creator
    def bulk_add_slides(
        self, 
        info: strawberry.types.Info, 
        content_id: strawberry.ID, 
        slides: List[SlideUploadInput]
    ) -> List[ContentMediaType]:
        # Verify ownership
        content = Content.objects.get(id=content_id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only add slides to your own content")
        
        created_media = []
        with transaction.atomic():
            for s in slides:
                media = ContentMedia.objects.create(
                    content_id=content_id,
                    media_type='image',
                    media_role='slideshow_image',
                    file_url=s.fileUrl,
                    slide_topic=s.title,
                    slide_hint=s.hint,
                    is_preview_slide=s.isPreview,
                    sort_order=s.sortOrder
                )
                created_media.append(ContentMediaType.from_model(media))

        return created_media

    @strawberry.mutation
    @require_creator
    def update_media(self, info: strawberry.types.Info, id: strawberry.ID, input: UpdateMediaInput) -> ContentMediaType:
        media = ContentMedia.objects.get(id=id)
        user = info.context.request.user
        if media.content.creator.user != user:
            raise Exception("You can only update media belonging to your content")
        
        if input.fileUrl is not None: media.file_url = input.fileUrl
        if input.fileName is not None: media.file_name = input.fileName
        if input.sortOrder is not None: media.sort_order = input.sortOrder
        if input.slideTopic is not None: media.slide_topic = input.slideTopic
        if input.slideHint is not None: media.slide_hint = input.slideHint
        if input.isPreviewSlide is not None: media.is_preview_slide = input.isPreviewSlide
        
        media.save()
        return ContentMediaType.from_model(media)

    @strawberry.mutation
    @require_creator
    def delete_media(self, info: strawberry.types.Info, id: strawberry.ID) -> bool:
        media = ContentMedia.objects.get(id=id)
        user = info.context.request.user
        if media.content.creator.user != user:
            raise Exception("You can only delete media belonging to your content")
        
        media.delete()
        return True

    @strawberry.mutation
    @require_creator
    def add_content_tag(self, info: strawberry.types.Info, content_id: strawberry.ID, tag: str) -> bool:
        # Verify ownership
        content = Content.objects.get(id=content_id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only add tags to your own content")
        ContentTag.objects.get_or_create(content_id=content_id, tag=tag.strip().lower())
        return True

    @strawberry.mutation
    @require_creator
    def add_content_attachment(self, info: strawberry.types.Info, content_id: strawberry.ID, input: AttachmentInput) -> ContentAttachmentType:
        # Verify ownership
        content = Content.objects.get(id=content_id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only add attachments to your own content")

        attachment = ContentAttachment.objects.create(
            content_id=content_id,
            attachment_type=input.attachmentType,
            file_url=input.fileUrl,
            file_name=input.fileName,
            title=getattr(input, 'title', None),
            description=getattr(input, 'description', None),
            file_size_bytes=input.fileSizeBytes,
            thumbnail_url=getattr(input, 'thumbnailUrl', None),
        )
        return ContentAttachmentType.from_model(attachment)

    @strawberry.mutation
    @require_creator
    def trim_content_video(self, info: strawberry.types.Info, input: TrimVideoInput) -> TrimVideoResult:
        """
        Server-side video trim.

        Delegates to the shared media_processor trim service so there is ONE
        tested trim path across the app (see
        lipaidox/media_processor/{video_ops,services}.py) rather than a second
        ffmpeg invocation maintained here. That path is frame-accurate
        (re-encode) and writes a streamable result, and it leaves the original
        file untouched so a trim can never destroy the source.
        """
        from lipaidox.media_processor.services import trim_content_media
        from lipaidox.media_processor.video_ops import VideoOpError

        user = info.context.request.user

        # ── Ownership ────────────────────────────────────────────────────────
        try:
            content = Content.objects.get(id=input.contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found.")
        if content.creator.user != user:
            raise Exception("You can only trim media belonging to your own content.")

        try:
            media_obj = ContentMedia.objects.get(id=input.mediaId)
        except ContentMedia.DoesNotExist:
            raise Exception("Media not found.")
        if media_obj.content_id != content.id:
            raise Exception("Media does not belong to the specified content.")
        if str(media_obj.media_type).lower() != "video":
            raise Exception("Only video media can be trimmed.")

        # ── Range validation (the service re-checks against real duration) ──
        start = float(input.startTime)
        end = float(input.endTime)
        if start < 0 or end <= start:
            raise Exception("Invalid trim range: endTime must be greater than startTime.")

        # ── Apply via the shared service ────────────────────────────────────
        try:
            media_obj = trim_content_media(media_obj, start, end)
        except VideoOpError as exc:
            logger.warning("trim_content_video failed for media %s: %s", input.mediaId, exc)
            raise Exception(f"Video trim failed: {exc}")

        return TrimVideoResult(
            mediaId=strawberry.ID(str(media_obj.id)),
            fileUrl=media_obj.file_url,
            durationSeconds=(
                float(media_obj.duration_seconds)
                if media_obj.duration_seconds is not None
                else None
            ),
            fileSizeBytes=media_obj.file_size_bytes,
        )
    @strawberry.mutation
    @require_creator
    def publish_content(self, info: strawberry.types.Info, id: strawberry.ID) -> ContentType:
        """Immediately publish a draft/scheduled content item."""
        from django.utils import timezone
        content = Content.objects.get(id=id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only publish your own content.")
        content.status = "published"
        content.scheduled_at = None
        if not content.published_at:
            content.published_at = timezone.now()
        content.save(update_fields=["status", "scheduled_at", "published_at"])
        _announce_if_published(content)
        return ContentType.from_model(content)

    @strawberry.mutation
    @require_creator
    def schedule_content(
        self,
        info: strawberry.types.Info,
        id: strawberry.ID,
        scheduled_at: str,
    ) -> ContentType:
        """Schedule a content item to be published at a future datetime (ISO-8601 string)."""
        from django.utils import timezone
        from datetime import datetime
        content = Content.objects.get(id=id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only schedule your own content.")
        try:
            dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise Exception(f"Invalid datetime format: {scheduled_at!r}. Use ISO-8601.")
        if dt <= timezone.now():
            raise Exception("Scheduled time must be in the future.")
        content.status = "scheduled"
        content.scheduled_at = dt
        content.save(update_fields=["status", "scheduled_at"])
        return ContentType.from_model(content)

    @strawberry.mutation
    @require_creator
    def duplicate_content(self, info: strawberry.types.Info, id: strawberry.ID) -> ContentType:
        """Duplicate a content item as a new draft."""
        content = Content.objects.get(id=id)
        user = info.context.request.user
        if content.creator.user != user:
            raise Exception("You can only duplicate your own content.")
        from multitenant.utils.tenant_context import get_current_tenant
        tenant = get_current_tenant()
        with transaction.atomic():
            new_content = Content.objects.create(
                creator=content.creator,
                tenant=tenant,
                title=f"Copy of {content.title}",
                description=content.description,
                content_format=content.content_format,
                status="draft",
                categories=content.categories,
                primary_category=content.primary_category,
                access_type=content.access_type,
                one_time_price=content.one_time_price,
                timed_price=content.timed_price,
                timed_duration_value=content.timed_duration_value,
                timed_duration_unit=content.timed_duration_unit,
                allow_download=content.allow_download,
                is_continuous=content.is_continuous,
                series=content.series,
                episode_number=content.episode_number,
            )
            # Copy tags
            for tag in content.tags_list.all():
                ContentTag.objects.create(content=new_content, tag=tag.tag)
            # Copy media references (same URLs, no re-upload needed)
            for media in content.media.all():
                ContentMedia.objects.create(
                    content=new_content,
                    media_type=media.media_type,
                    media_role=media.media_role,
                    file_url=media.file_url,
                    file_name=media.file_name,
                    file_size_bytes=media.file_size_bytes,
                    sort_order=media.sort_order,
                )
            ContentAccessRule.objects.create(content=new_content, allow_download=content.allow_download)
        return ContentType.from_model(new_content)
