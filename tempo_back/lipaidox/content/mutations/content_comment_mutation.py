import strawberry
from django.utils import timezone

from ..models import ContentComment, ContentCommentStatus
from ..schema.content_comment_schema import (
    CreateContentCommentPayload,
    DeleteContentCommentPayload,
)
from ..queries.content_review_query import get_content
from ..queries.content_comment_query import build_content_comment_type

BODY_MIN, BODY_MAX = 1, 2000


def _require_user(info):
    user = info.context.request.user
    if not getattr(user, "is_authenticated", False):
        raise Exception("Authentication required")
    return user


@strawberry.type
class ContentCommentMutation:
    @strawberry.mutation
    def create_content_comment(
        self, info, content_id: strawberry.ID, body: str
    ) -> CreateContentCommentPayload:
        user = _require_user(info)
        content = get_content(content_id)
        clean = (body or "").strip()
        if len(clean) < BODY_MIN:
            raise Exception("Comment cannot be empty")
        if len(clean) > BODY_MAX:
            raise Exception(f"Comment must be at most {BODY_MAX} characters")
        comment = ContentComment.objects.create(
            author=user, content=content, tenant=getattr(user, "tenant", None),
            body=clean, status=ContentCommentStatus.PUBLISHED,
        )
        return CreateContentCommentPayload(comment=build_content_comment_type(comment))

    @strawberry.mutation
    def delete_content_comment(self, info, comment_id: strawberry.ID) -> DeleteContentCommentPayload:
        user = _require_user(info)
        comment = (
            ContentComment.objects.filter(id=comment_id, deleted_at__isnull=True)
            .select_related("content__creator")
            .first()
        )
        if comment is None:
            return DeleteContentCommentPayload(success=True)
        is_author = str(comment.author_id) == str(user.id)
        creator = comment.content.creator if comment.content else None
        is_content_owner = creator is not None and str(creator.user_id) == str(user.id)
        if not (is_author or is_content_owner):
            raise Exception("You can only delete your own comments")
        comment.deleted_at = timezone.now()
        comment.status = ContentCommentStatus.HIDDEN
        comment.save(update_fields=["deleted_at", "status", "updated_at"])
        return DeleteContentCommentPayload(success=True)
