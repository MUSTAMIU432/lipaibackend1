import strawberry

from ..models import ContentComment, ContentCommentStatus
from ..schema.content_comment_schema import (
    ContentCommentType,
    ContentCommentAuthorType,
    ContentCommentListType,
)
from .content_review_query import get_content


def published_comments(content):
    return ContentComment.objects.filter(
        content=content, status=ContentCommentStatus.PUBLISHED, deleted_at__isnull=True
    )


def build_content_comment_type(comment) -> ContentCommentType:
    author = comment.author
    profile = getattr(author, "profile", None)
    return ContentCommentType(
        id=strawberry.ID(str(comment.id)),
        author=ContentCommentAuthorType(
            id=strawberry.ID(str(author.id)),
            username=author.username,
            displayName=(profile.username if profile else author.username),
            avatar=(profile.profile_photo_url if profile else None),
            isVerified=(profile.is_verified if profile else False),
        ),
        body=comment.body,
        status=comment.status,
        createdAt=comment.created_at,
        updatedAt=comment.updated_at,
    )


@strawberry.type
class ContentCommentQuery:
    @strawberry.field
    def content_comments(
        self, info, content_id: strawberry.ID, offset: int = 0, limit: int = 20
    ) -> ContentCommentListType:
        content = get_content(content_id)
        qs = (
            published_comments(content)
            .select_related("author", "author__profile")
            .order_by("-created_at")
        )
        total = qs.count()
        page = list(qs[offset:offset + limit])
        return ContentCommentListType(
            items=[build_content_comment_type(c) for c in page], totalCount=total,
        )
