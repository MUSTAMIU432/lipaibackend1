import strawberry
from typing import Optional
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone

from ..models import ContentReview, ContentReviewStatus, ContentReviewHelpful
from ..schema.content_review_schema import (
    CreateContentReviewPayload,
    UpdateContentReviewPayload,
    DeleteContentReviewPayload,
    MarkContentReviewHelpfulPayload,
    ReportContentReviewPayload,
    ReplyToContentReviewPayload,
    DeleteContentReviewReplyPayload,
)
from ..queries.content_review_query import get_content, build_content_review_type

BODY_MIN, BODY_MAX, TITLE_MAX = 3, 5000, 120
REPLY_MAX = 2000


def _viewer_helpful_set(review, user) -> set:
    if ContentReviewHelpful.objects.filter(review=review, user=user).exists():
        return {str(review.id)}
    return set()


def _require_content_owner(review, user):
    creator = review.content.creator if review.content else None
    if creator is None or str(creator.user_id) != str(user.id):
        raise Exception("Only the content owner can reply to reviews")


def _require_user(info):
    user = info.context.request.user
    if not getattr(user, "is_authenticated", False):
        raise Exception("Authentication required")
    return user


def _validate(rating: int, title: Optional[str], body: str) -> str:
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise Exception("Rating must be an integer between 1 and 5")
    if title and len(title) > TITLE_MAX:
        raise Exception(f"Title must be at most {TITLE_MAX} characters")
    body = (body or "").strip()
    if len(body) < BODY_MIN:
        raise Exception(f"Review must be at least {BODY_MIN} characters")
    if len(body) > BODY_MAX:
        raise Exception(f"Review must be at most {BODY_MAX} characters")
    return body


@strawberry.type
class ContentReviewMutation:
    @strawberry.mutation
    def create_content_review(
        self, info, content_id: strawberry.ID, rating: int, body: str, title: Optional[str] = None
    ) -> CreateContentReviewPayload:
        user = _require_user(info)
        content = get_content(content_id)
        if content.creator and str(content.creator.user_id) == str(user.id):
            raise Exception("You cannot review your own content")
        clean_body = _validate(rating, title, body)
        try:
            with transaction.atomic():
                review = ContentReview.objects.create(
                    author=user, content=content, tenant=getattr(user, "tenant", None),
                    rating=rating, title=(title or "").strip(), body=clean_body,
                    status=ContentReviewStatus.PUBLISHED, is_verified=False,
                )
        except IntegrityError:
            raise Exception("You have already reviewed this content")
        return CreateContentReviewPayload(review=build_content_review_type(review, set()))

    @strawberry.mutation
    def update_content_review(
        self, info, review_id: strawberry.ID, rating: Optional[int] = None,
        body: Optional[str] = None, title: Optional[str] = None,
    ) -> UpdateContentReviewPayload:
        user = _require_user(info)
        review = ContentReview.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        if str(review.author_id) != str(user.id):
            raise Exception("You can only edit your own review")
        new_rating = rating if rating is not None else review.rating
        new_body = body if body is not None else review.body
        clean_body = _validate(new_rating, title if title is not None else review.title, new_body)
        review.rating = new_rating
        review.body = clean_body
        if title is not None:
            review.title = title.strip()
        review.edited_at = timezone.now()
        review.save(update_fields=["rating", "body", "title", "edited_at", "updated_at"])
        helpful = {str(review.id)} if ContentReviewHelpful.objects.filter(review=review, user=user).exists() else set()
        return UpdateContentReviewPayload(review=build_content_review_type(review, helpful))

    @strawberry.mutation
    def delete_content_review(self, info, review_id: strawberry.ID) -> DeleteContentReviewPayload:
        user = _require_user(info)
        review = ContentReview.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            return DeleteContentReviewPayload(success=True)
        if str(review.author_id) != str(user.id):
            raise Exception("You can only delete your own review")
        review.deleted_at = timezone.now()
        review.status = ContentReviewStatus.HIDDEN
        review.save(update_fields=["deleted_at", "status", "updated_at"])
        return DeleteContentReviewPayload(success=True)

    @strawberry.mutation
    def mark_content_review_helpful(self, info, review_id: strawberry.ID) -> MarkContentReviewHelpfulPayload:
        user = _require_user(info)
        review = ContentReview.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        with transaction.atomic():
            _, created = ContentReviewHelpful.objects.get_or_create(
                review=review, user=user, defaults={"tenant": getattr(user, "tenant", None)}
            )
            if created:
                ContentReview.objects.filter(id=review.id).update(helpful_count=F("helpful_count") + 1)
            review.refresh_from_db(fields=["helpful_count"])
        return MarkContentReviewHelpfulPayload(helpfulCount=review.helpful_count, viewerHasMarkedHelpful=True)

    @strawberry.mutation
    def remove_content_review_helpful(self, info, review_id: strawberry.ID) -> MarkContentReviewHelpfulPayload:
        user = _require_user(info)
        review = ContentReview.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        with transaction.atomic():
            deleted, _ = ContentReviewHelpful.objects.filter(review=review, user=user).delete()
            if deleted:
                ContentReview.objects.filter(id=review.id, helpful_count__gt=0).update(helpful_count=F("helpful_count") - 1)
            review.refresh_from_db(fields=["helpful_count"])
        return MarkContentReviewHelpfulPayload(helpfulCount=review.helpful_count, viewerHasMarkedHelpful=False)

    @strawberry.mutation
    def reply_to_content_review(self, info, review_id: strawberry.ID, body: str) -> ReplyToContentReviewPayload:
        user = _require_user(info)
        review = (
            ContentReview.objects.filter(id=review_id, deleted_at__isnull=True)
            .select_related("content__creator")
            .first()
        )
        if review is None:
            raise Exception("Review not found")
        _require_content_owner(review, user)
        clean = (body or "").strip()
        if not clean:
            raise Exception("Reply cannot be empty")
        if len(clean) > REPLY_MAX:
            raise Exception(f"Reply must be at most {REPLY_MAX} characters")
        review.owner_reply = clean
        if review.owner_replied_at:
            review.owner_reply_edited_at = timezone.now()
        else:
            review.owner_replied_at = timezone.now()
        review.save(update_fields=["owner_reply", "owner_replied_at", "owner_reply_edited_at", "updated_at"])
        return ReplyToContentReviewPayload(review=build_content_review_type(review, _viewer_helpful_set(review, user)))

    @strawberry.mutation
    def delete_content_review_reply(self, info, review_id: strawberry.ID) -> DeleteContentReviewReplyPayload:
        user = _require_user(info)
        review = (
            ContentReview.objects.filter(id=review_id, deleted_at__isnull=True)
            .select_related("content__creator")
            .first()
        )
        if review is None:
            raise Exception("Review not found")
        _require_content_owner(review, user)
        review.owner_reply = ""
        review.owner_replied_at = None
        review.owner_reply_edited_at = None
        review.save(update_fields=["owner_reply", "owner_replied_at", "owner_reply_edited_at", "updated_at"])
        return DeleteContentReviewReplyPayload(review=build_content_review_type(review, _viewer_helpful_set(review, user)))

    @strawberry.mutation
    def report_content_review(self, info, review_id: strawberry.ID, reason: Optional[str] = None) -> ReportContentReviewPayload:
        _require_user(info)
        review = ContentReview.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        review.status = ContentReviewStatus.FLAGGED
        review.save(update_fields=["status", "updated_at"])
        return ReportContentReviewPayload(success=True)
