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
        Server-side video trim using FFmpeg.
        Reads the existing media file, trims to [startTime, endTime],
        saves the result as a new file, and updates the ContentMedia record.
        """
        import os
        import uuid
        import subprocess
        from django.conf import settings

        user = info.context.request.user

        # Ownership checks
        content = Content.objects.get(id=input.contentId)
        if content.creator.user != user:
            raise Exception("You can only trim media belonging to your own content.")

        media_obj = ContentMedia.objects.get(id=input.mediaId)
        if media_obj.content_id != content.id:
            raise Exception("Media does not belong to the specified content.")

        # Validate trim range
        start = float(input.startTime)
        end = float(input.endTime)
        if start < 0 or end <= start:
            raise Exception("Invalid trim range: endTime must be greater than startTime.")
        if (end - start) < 0.1:
            raise Exception("Trim duration must be at least 0.1 seconds.")

        # Resolve source file path from URL
        media_url = media_obj.file_url  # e.g. "/media/content/<uid>/abc.mp4"
        media_root = str(settings.MEDIA_ROOT)
        media_url_prefix = settings.MEDIA_URL  # "/media/"

        if media_url.startswith(media_url_prefix):
            rel_path = media_url[len(media_url_prefix):]
        else:
            rel_path = media_url.lstrip("/")
        src_path = os.path.join(media_root, rel_path)

        if not os.path.isfile(src_path):
            raise Exception(f"Source media file not found on server: {rel_path}")

        # Resolve FFmpeg binary (system or bundled via imageio_ffmpeg)
        ffmpeg_bin = "ffmpeg"
        try:
            import shutil
            if not shutil.which("ffmpeg"):
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        # Output file alongside original
        src_dir = os.path.dirname(src_path)
        src_ext = os.path.splitext(src_path)[1] or ".mp4"
        out_name = f"{uuid.uuid4().hex}-trimmed{src_ext}"
        out_path = os.path.join(src_dir, out_name)

        duration = end - start
        ffmpeg_cmd = [
            ffmpeg_bin,
            "-y",                      # overwrite
            "-ss", str(start),         # seek BEFORE input for speed
            "-t",  str(duration),
            "-i",  src_path,
            "-c:v", "copy",            # stream copy — no re-encode, fast
            "-c:a", "copy",
            "-avoid_negative_ts", "make_zero",
            out_path,
        ]
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error("ffmpeg trim failed: %s", result.stderr[-1000:])
                raise Exception("FFmpeg trim failed. " + (result.stderr[-300:] if result.stderr else ""))
        except subprocess.TimeoutExpired:
            raise Exception("Video trim timed out (>5 min). Try a shorter clip.")

        # Get output file info
        out_size = os.path.getsize(out_path)

        # Compute output duration via ffprobe (best-effort)
        out_duration: Optional[float] = None
        try:
            probe_bin = ffmpeg_bin.replace("ffmpeg", "ffprobe")
            if not os.path.isfile(probe_bin):
                probe_bin = "ffprobe"
            probe_cmd = [
                probe_bin, "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                out_path,
            ]
            probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=15)
            out_duration = float(probe.stdout.strip()) if probe.stdout.strip() else None
        except Exception:
            out_duration = duration  # fallback to requested duration

        # Build new media URL
        user_dir_rel = os.path.relpath(src_dir, media_root)
        out_url = f"{media_url_prefix}{user_dir_rel}/{out_name}".replace("\\", "/")

        # Update the ContentMedia record to point to the trimmed file
        with transaction.atomic():
            media_obj.file_url = out_url
            media_obj.file_size_bytes = out_size
            if out_duration is not None:
                media_obj.duration_seconds = int(round(out_duration))
            media_obj.save(update_fields=["file_url", "file_size_bytes", "duration_seconds"])

        return TrimVideoResult(
            mediaId=strawberry.ID(str(media_obj.id)),
            fileUrl=out_url,
            durationSeconds=out_duration,
            fileSizeBytes=out_size,
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
