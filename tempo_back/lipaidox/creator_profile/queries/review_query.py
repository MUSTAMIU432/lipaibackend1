import strawberry
from typing import Optional

from ..models import Review, ReviewStatus, ReviewHelpful
from ..schema.review_schema import (
    ReviewType,
    ReviewAuthorType,
    ReviewOwnerReplyType,
    ReviewListType,
    ReviewSummaryType,
    RatingDistributionType,
    ReviewEligibilityType,
)
from ..services.social_service import get_target_profile, review_summary, published_reviews


def build_review_type(review: Review, viewer_helpful_ids: set) -> ReviewType:
    author = review.author
    profile = getattr(author, "profile", None)
    return ReviewType(
        id=strawberry.ID(str(review.id)),
        author=ReviewAuthorType(
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
            ReviewOwnerReplyType(
                body=review.owner_reply,
                createdAt=review.owner_replied_at,
                editedAt=review.owner_reply_edited_at,
            )
            if review.owner_reply and review.owner_replied_at
            else None
        ),
    )


_SORTS = {
    "newest": "-created_at",
    "oldest": "created_at",
    "highest": "-rating",
    "lowest": "rating",
    "helpful": "-helpful_count",
}


@strawberry.type
class ReviewQuery:
    @strawberry.field
    def reviews(
        self,
        info,
        target_user_id: strawberry.ID,
        rating: Optional[int] = None,
        verified_only: Optional[bool] = None,
        sort: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> ReviewListType:
        profile = get_target_profile(target_user_id)
        qs = published_reviews(profile).select_related("author", "author__profile")
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
                str(rid)
                for rid in ReviewHelpful.objects.filter(
                    user=user, review_id__in=[r.id for r in page]
                ).values_list("review_id", flat=True)
            }

        return ReviewListType(
            items=[build_review_type(r, viewer_helpful_ids) for r in page],
            totalCount=total,
        )

    @strawberry.field
    def review_summary(self, info, target_user_id: strawberry.ID) -> ReviewSummaryType:
        profile = get_target_profile(target_user_id)
        s = review_summary(profile)
        return ReviewSummaryType(
            averageRating=s["averageRating"],
            totalReviews=s["totalReviews"],
            verifiedReviews=s["verifiedReviews"],
            ratingDistribution=RatingDistributionType(
                oneStar=s["oneStar"], twoStar=s["twoStar"], threeStar=s["threeStar"],
                fourStar=s["fourStar"], fiveStar=s["fiveStar"],
            ),
        )

    @strawberry.field
    def my_reviews(self, info, offset: int = 0, limit: int = 20) -> ReviewListType:
        user = info.context.request.user
        if not getattr(user, "is_authenticated", False):
            return ReviewListType(items=[], totalCount=0)
        qs = (
            Review.objects.filter(author=user, deleted_at__isnull=True)
            .select_related("author", "author__profile")
            .order_by("-created_at")
        )
        total = qs.count()
        page = list(qs[offset:offset + limit])
        helpful_ids = {
            str(rid)
            for rid in ReviewHelpful.objects.filter(user=user, review_id__in=[r.id for r in page]).values_list("review_id", flat=True)
        }
        return ReviewListType(items=[build_review_type(r, helpful_ids) for r in page], totalCount=total)

    @strawberry.field
    def review_eligibility(self, info, target_user_id: strawberry.ID) -> ReviewEligibilityType:
        profile = get_target_profile(target_user_id)
        user = info.context.request.user
        if not getattr(user, "is_authenticated", False):
            return ReviewEligibilityType(canReview=False, hasReviewed=False, reason="You must sign in to leave a review.")
        if str(profile.user_id) == str(user.id):
            return ReviewEligibilityType(canReview=False, hasReviewed=False, reason="You cannot review your own profile.")
        has = Review.objects.filter(author=user, target=profile, deleted_at__isnull=True).exists()
        if has:
            return ReviewEligibilityType(canReview=False, hasReviewed=True, reason="You have already reviewed this creator.")
        return ReviewEligibilityType(canReview=True, hasReviewed=False)
