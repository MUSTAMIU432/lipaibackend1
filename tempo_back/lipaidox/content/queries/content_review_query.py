import strawberry
from typing import Optional
from django.db.models import Avg, Count, Q

from ..models import Content, ContentReview, ContentReviewStatus, ContentReviewHelpful
from ..schema.content_review_schema import (
    ContentReviewType,
    ContentReviewAuthorType,
    ContentReviewOwnerReplyType,
    ContentReviewListType,
    ContentReviewSummaryType,
    ContentRatingDistributionType,
    ContentReviewEligibilityType,
)

_SORTS = {"newest": "-created_at", "oldest": "created_at", "highest": "-rating", "lowest": "rating", "helpful": "-helpful_count"}


def get_content(content_id):
    try:
        return Content.objects.select_related("creator").get(id=content_id)
    except Content.DoesNotExist:
        raise Exception("Content not found")


def published_reviews(content):
    return ContentReview.objects.filter(content=content, status=ContentReviewStatus.PUBLISHED, deleted_at__isnull=True)


def build_content_review_type(review, viewer_helpful_ids: set) -> ContentReviewType:
    author = review.author
    profile = getattr(author, "profile", None)
    return ContentReviewType(
        id=strawberry.ID(str(review.id)),
        author=ContentReviewAuthorType(
            id=strawberry.ID(str(author.id)),
            username=author.username,
            displayName=(profile.username if profile else author.username),
            avatar=(profile.profile_photo_url if profile else None),
            isVerified=(profile.is_verified if profile else False),
        ),
        rating=review.rating,
        title=review.title or None,
        body=review.body,
        status=review.status,
        isVerified=review.is_verified,
        helpfulCount=review.helpful_count,
        viewerHasMarkedHelpful=str(review.id) in viewer_helpful_ids,
        createdAt=review.created_at,
        updatedAt=review.updated_at,
        editedAt=review.edited_at,
        ownerReply=(
            ContentReviewOwnerReplyType(
                body=review.owner_reply,
                createdAt=review.owner_replied_at,
                editedAt=review.owner_reply_edited_at,
            )
            if review.owner_reply and review.owner_replied_at
            else None
        ),
    )


def content_review_summary(content) -> dict:
    agg = published_reviews(content).aggregate(
        avg=Avg("rating"), total=Count("id"), verified=Count("id", filter=Q(is_verified=True)),
        one=Count("id", filter=Q(rating=1)), two=Count("id", filter=Q(rating=2)),
        three=Count("id", filter=Q(rating=3)), four=Count("id", filter=Q(rating=4)), five=Count("id", filter=Q(rating=5)),
    )
    return {
        "averageRating": round(float(agg["avg"] or 0.0), 2),
        "totalReviews": agg["total"] or 0, "verifiedReviews": agg["verified"] or 0,
        "one": agg["one"] or 0, "two": agg["two"] or 0, "three": agg["three"] or 0,
        "four": agg["four"] or 0, "five": agg["five"] or 0,
    }


@strawberry.type
class ContentReviewQuery:
    @strawberry.field
    def content_reviews(
        self, info, content_id: strawberry.ID, rating: Optional[int] = None,
        verified_only: Optional[bool] = None, sort: Optional[str] = None,
        offset: int = 0, limit: int = 20,
    ) -> ContentReviewListType:
        content = get_content(content_id)
        qs = published_reviews(content).select_related("author", "author__profile")
        if rating is not None:
            qs = qs.filter(rating=rating)
        if verified_only:
            qs = qs.filter(is_verified=True)
        qs = qs.order_by(_SORTS.get((sort or "newest").lower(), "-created_at"))
        total = qs.count()
        page = list(qs[offset:offset + limit])

        viewer_helpful_ids: set = set()
        user = info.context.request.user
        if getattr(user, "is_authenticated", False) and page:
            viewer_helpful_ids = {
                str(rid) for rid in ContentReviewHelpful.objects.filter(
                    user=user, review_id__in=[r.id for r in page]
                ).values_list("review_id", flat=True)
            }
        return ContentReviewListType(
            items=[build_content_review_type(r, viewer_helpful_ids) for r in page], totalCount=total,
        )

    @strawberry.field
    def content_review_summary(self, info, content_id: strawberry.ID) -> ContentReviewSummaryType:
        content = get_content(content_id)
        s = content_review_summary(content)
        return ContentReviewSummaryType(
            averageRating=s["averageRating"], totalReviews=s["totalReviews"], verifiedReviews=s["verifiedReviews"],
            ratingDistribution=ContentRatingDistributionType(
                oneStar=s["one"], twoStar=s["two"], threeStar=s["three"], fourStar=s["four"], fiveStar=s["five"],
            ),
        )

    @strawberry.field
    def content_review_eligibility(self, info, content_id: strawberry.ID) -> ContentReviewEligibilityType:
        content = get_content(content_id)
        user = info.context.request.user
        if not getattr(user, "is_authenticated", False):
            return ContentReviewEligibilityType(canReview=False, hasReviewed=False, reason="You must sign in to leave a review.")
        if content.creator and str(content.creator.user_id) == str(user.id):
            return ContentReviewEligibilityType(canReview=False, hasReviewed=False, reason="You cannot review your own content.")
        has = ContentReview.objects.filter(author=user, content=content, deleted_at__isnull=True).exists()
        if has:
            return ContentReviewEligibilityType(canReview=False, hasReviewed=True, reason="You have already reviewed this content.")
        return ContentReviewEligibilityType(canReview=True, hasReviewed=False)
