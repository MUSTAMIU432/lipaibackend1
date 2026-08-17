"""Like / save (bookmark) toggles for content, with a live `like_count`."""
import strawberry
from typing import List, Optional
from django.db.models import F

from ..models import Content, ContentLike, ContentBookmark
from ..schema.content_schema import ContentType


def _require_user(info):
    user = info.context.request.user
    if not getattr(user, "is_authenticated", False):
        raise Exception("Authentication required")
    return user


def _get_content(user, content_id):
    try:
        return Content.objects.get(id=content_id, tenant=user.tenant)
    except Content.DoesNotExist:
        raise Exception("Content not found")


def _is_saved(user, content) -> bool:
    return ContentBookmark.objects.filter(user=user, content=content).exists()


@strawberry.type
class ContentInteractionResult:
    contentId: strawberry.ID
    liked: bool
    saved: bool
    likeCount: int


def _result(content, liked: bool, saved: bool) -> "ContentInteractionResult":
    content.refresh_from_db(fields=["like_count"])
    return ContentInteractionResult(
        contentId=strawberry.ID(str(content.id)),
        liked=liked,
        saved=saved,
        likeCount=content.like_count,
    )


@strawberry.type
class ContentInteractionMutation:
    @strawberry.mutation
    def like_content(self, info: strawberry.types.Info, content_id: strawberry.ID) -> ContentInteractionResult:
        user = _require_user(info)
        content = _get_content(user, content_id)
        _, created = ContentLike.objects.get_or_create(
            user=user, content=content, defaults={"tenant": getattr(user, "tenant", None)}
        )
        if created:
            Content.objects.filter(id=content.id).update(like_count=F("like_count") + 1)
        return _result(content, liked=True, saved=_is_saved(user, content))

    @strawberry.mutation
    def unlike_content(self, info: strawberry.types.Info, content_id: strawberry.ID) -> ContentInteractionResult:
        user = _require_user(info)
        content = _get_content(user, content_id)
        deleted, _ = ContentLike.objects.filter(user=user, content=content).delete()
        if deleted:
            Content.objects.filter(id=content.id, like_count__gt=0).update(like_count=F("like_count") - 1)
        return _result(content, liked=False, saved=_is_saved(user, content))

    @strawberry.mutation
    def save_content(self, info: strawberry.types.Info, content_id: strawberry.ID) -> ContentInteractionResult:
        user = _require_user(info)
        content = _get_content(user, content_id)
        ContentBookmark.objects.get_or_create(
            user=user, content=content, defaults={"tenant": getattr(user, "tenant", None)}
        )
        return _result(content, liked=ContentLike.objects.filter(user=user, content=content).exists(), saved=True)

    @strawberry.mutation
    def unsave_content(self, info: strawberry.types.Info, content_id: strawberry.ID) -> ContentInteractionResult:
        user = _require_user(info)
        content = _get_content(user, content_id)
        ContentBookmark.objects.filter(user=user, content=content).delete()
        return _result(content, liked=ContentLike.objects.filter(user=user, content=content).exists(), saved=False)


@strawberry.type
class ContentInteractionQuery:
    @strawberry.field
    def my_saved_content(
        self, info: strawberry.types.Info, offset: int = 0, limit: int = 20
    ) -> List[ContentType]:
        """The signed-in user's saved/bookmarked content, newest first."""
        user = _require_user(info)
        rows = (
            ContentBookmark.objects.filter(user=user)
            .select_related("content")
            .order_by("-created_at")[offset:offset + limit]
        )
        return [ContentType.from_model(b.content) for b in rows]
