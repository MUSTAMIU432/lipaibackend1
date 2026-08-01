import strawberry
from typing import Optional
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone

from ..models import Review, ReviewStatus, ReviewHelpful, ReviewReport
from ..schema.review_schema import (
    CreateReviewPayload,
    UpdateReviewPayload,
    DeleteReviewPayload,
    MarkReviewHelpfulPayload,
    ReportReviewPayload,
    ReplyToReviewPayload,
    DeleteReviewReplyPayload,
)
from ..services.social_service import require_user, get_target_profile
from ..queries.review_query import build_review_type

TITLE_MAX = 120
BODY_MIN = 3
BODY_MAX = 5000
REPLY_MAX = 2000


def _viewer_helpful_set(review, user) -> set:
    if ReviewHelpful.objects.filter(review=review, user=user).exists():
        return {str(review.id)}
    return set()


def _require_review_target_owner(review, user):
    if str(review.target.user_id) != str(user.id):
        raise Exception("Only the reviewed creator can reply to reviews")


def _validate(rating: int, title: Optional[str], body: str):
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
class ReviewMutation:
    @strawberry.mutation
    def create_review(
        self, info, target_user_id: strawberry.ID, rating: int, body: str, title: Optional[str] = None
    ) -> CreateReviewPayload:
        user = require_user(info)
        profile = get_target_profile(target_user_id)
        if str(profile.user_id) == str(user.id):
            raise Exception("You cannot review your own profile")
        clean_body = _validate(rating, title, body)
        try:
            with transaction.atomic():
                review = Review.objects.create(
                    author=user,
                    target=profile,
                    tenant=getattr(user, "tenant", None),
                    rating=rating,
                    title=(title or "").strip(),
                    body=clean_body,
                    status=ReviewStatus.PUBLISHED,
                    is_verified=False,
                )
        except IntegrityError:
            raise Exception("You have already reviewed this creator")
        return CreateReviewPayload(review=build_review_type(review, set()))

    @strawberry.mutation
    def update_review(
        self, info, review_id: strawberry.ID, rating: Optional[int] = None,
        body: Optional[str] = None, title: Optional[str] = None,
    ) -> UpdateReviewPayload:
        user = require_user(info)
        review = Review.objects.filter(id=review_id, deleted_at__isnull=True).first()
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
        helpful = {str(review.id)} if ReviewHelpful.objects.filter(review=review, user=user).exists() else set()
        return UpdateReviewPayload(review=build_review_type(review, helpful))

    @strawberry.mutation
    def delete_review(self, info, review_id: strawberry.ID) -> DeleteReviewPayload:
        user = require_user(info)
        review = Review.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            return DeleteReviewPayload(success=True)  # idempotent
        if str(review.author_id) != str(user.id):
            raise Exception("You can only delete your own review")
        review.deleted_at = timezone.now()
        review.status = ReviewStatus.HIDDEN
        review.save(update_fields=["deleted_at", "status", "updated_at"])
        return DeleteReviewPayload(success=True)

    @strawberry.mutation
    def mark_review_helpful(self, info, review_id: strawberry.ID) -> MarkReviewHelpfulPayload:
        user = require_user(info)
        review = Review.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        with transaction.atomic():
            _, created = ReviewHelpful.objects.get_or_create(
                review=review, user=user, defaults={"tenant": getattr(user, "tenant", None)}
            )
            if created:
                Review.objects.filter(id=review.id).update(helpful_count=F("helpful_count") + 1)
            review.refresh_from_db(fields=["helpful_count"])
        return MarkReviewHelpfulPayload(helpfulCount=review.helpful_count, viewerHasMarkedHelpful=True)

    @strawberry.mutation
    def remove_review_helpful(self, info, review_id: strawberry.ID) -> MarkReviewHelpfulPayload:
        user = require_user(info)
        review = Review.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        with transaction.atomic():
            deleted, _ = ReviewHelpful.objects.filter(review=review, user=user).delete()
            if deleted:
                Review.objects.filter(id=review.id, helpful_count__gt=0).update(helpful_count=F("helpful_count") - 1)
            review.refresh_from_db(fields=["helpful_count"])
        return MarkReviewHelpfulPayload(helpfulCount=review.helpful_count, viewerHasMarkedHelpful=False)

    @strawberry.mutation
    def reply_to_review(self, info, review_id: strawberry.ID, body: str) -> ReplyToReviewPayload:
        user = require_user(info)
        review = (
            Review.objects.filter(id=review_id, deleted_at__isnull=True)
            .select_related("target")
            .first()
        )
        if review is None:
            raise Exception("Review not found")
        _require_review_target_owner(review, user)
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
        return ReplyToReviewPayload(review=build_review_type(review, _viewer_helpful_set(review, user)))

    @strawberry.mutation
    def delete_review_reply(self, info, review_id: strawberry.ID) -> DeleteReviewReplyPayload:
        user = require_user(info)
        review = (
            Review.objects.filter(id=review_id, deleted_at__isnull=True)
            .select_related("target")
            .first()
        )
        if review is None:
            raise Exception("Review not found")
        _require_review_target_owner(review, user)
        review.owner_reply = ""
        review.owner_replied_at = None
        review.owner_reply_edited_at = None
        review.save(update_fields=["owner_reply", "owner_replied_at", "owner_reply_edited_at", "updated_at"])
        return DeleteReviewReplyPayload(review=build_review_type(review, _viewer_helpful_set(review, user)))

    @strawberry.mutation
    def report_review(self, info, review_id: strawberry.ID, reason: Optional[str] = None) -> ReportReviewPayload:
        user = require_user(info)
        review = Review.objects.filter(id=review_id, deleted_at__isnull=True).first()
        if review is None:
            raise Exception("Review not found")
        ReviewReport.objects.create(
            review=review, reporter=user, reason=(reason or "")[:255], tenant=getattr(user, "tenant", None)
        )
        return ReportReviewPayload(success=True)
