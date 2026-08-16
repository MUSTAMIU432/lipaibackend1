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


def build_content_comment_type(comment, reply_count: int = 0) -> ContentCommentType:
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
        parentId=(strawberry.ID(str(comment.parent_id)) if comment.parent_id else None),
        replyCount=reply_count,
    )


@strawberry.type
class ContentCommentQuery:
    @strawberry.field
    def content_comments(
        self, info, content_id: strawberry.ID, offset: int = 0, limit: int = 20
    ) -> ContentCommentListType:
        """Top-level comments only, newest first, each annotated with its reply count.

        Replies are fetched separately via `contentCommentReplies` so the client
        can lazily reveal them ("View N replies") the way YouTube does.
        """
        from django.db.models import Count, Q
        content = get_content(content_id)
        qs = (
            published_comments(content)
            .filter(parent__isnull=True)
            .select_related("author", "author__profile")
            .annotate(
                reply_count=Count(
                    "replies",
                    filter=Q(
                        replies__status=ContentCommentStatus.PUBLISHED,
                        replies__deleted_at__isnull=True,
                    ),
                )
            )
            .order_by("-created_at")
        )
        total = qs.count()
        page = list(qs[offset:offset + limit])
        return ContentCommentListType(
            items=[build_content_comment_type(c, getattr(c, "reply_count", 0)) for c in page],
            totalCount=total,
        )

    @strawberry.field
    def content_comment_replies(
        self, info, comment_id: strawberry.ID, offset: int = 0, limit: int = 20
    ) -> ContentCommentListType:
        """Published replies to a top-level comment, oldest first (conversation order)."""
        parent = ContentComment.objects.filter(
            id=comment_id, deleted_at__isnull=True
        ).first()
        if parent is None:
            return ContentCommentListType(items=[], totalCount=0)
        qs = (
            ContentComment.objects.filter(
                parent_id=parent.id,
                status=ContentCommentStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
            .select_related("author", "author__profile")
            .order_by("created_at")
        )
        total = qs.count()
        page = list(qs[offset:offset + limit])
        return ContentCommentListType(
            items=[build_content_comment_type(c) for c in page], totalCount=total,
        )
