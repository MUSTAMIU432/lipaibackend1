"""
Celery tasks for content media processing.

`content_mutation` enqueues `process_media_pipeline_task` when main video
media is created. This module was referenced but missing; a no-op task keeps
GraphQL create flows working until a full pipeline is implemented.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="lipaidox.media_processor.process_media_pipeline_task")
def process_media_pipeline_task(
    content_type_id: int,
    media_id: int,
    user_id: int,
) -> None:
    """
    Placeholder pipeline: extend with transcoding, poster frames, HLS, etc.

    Args match `ContentMutation` / `add_content_media` (ContentType id for
    ContentMedia, ContentMedia pk, User pk).
    """
    logger.info(
        "process_media_pipeline_task (placeholder): content_type_id=%s media_id=%s user_id=%s",
        content_type_id,
        media_id,
        user_id,
    )
