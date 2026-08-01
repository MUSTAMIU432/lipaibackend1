import strawberry
from typing import Optional
from datetime import datetime


@strawberry.type
class ReviewAuthorType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool


@strawberry.type
class ReviewOwnerReplyType:
    body: str
    createdAt: datetime
    editedAt: Optional[datetime]


@strawberry.type
class ReviewType:
    id: strawberry.ID
    author: ReviewAuthorType
    rating: int
    title: Optional[str]
    body: str
    status: str
    isVerified: bool
    helpfulCount: int
    viewerHasMarkedHelpful: bool
    createdAt: datetime
    updatedAt: datetime
    editedAt: Optional[datetime]
    ownerReply: Optional[ReviewOwnerReplyType] = None


@strawberry.type
class ReviewListType:
    items: list[ReviewType]
    totalCount: int


@strawberry.type
class RatingDistributionType:
    oneStar: int
    twoStar: int
    threeStar: int
    fourStar: int
    fiveStar: int


@strawberry.type
class ReviewSummaryType:
    averageRating: float
    totalReviews: int
    verifiedReviews: int
    ratingDistribution: RatingDistributionType


@strawberry.type
class ReviewEligibilityType:
    canReview: bool
    hasReviewed: bool
    reason: Optional[str] = None


@strawberry.type
class CreateReviewPayload:
    review: ReviewType


@strawberry.type
class UpdateReviewPayload:
    review: ReviewType


@strawberry.type
class DeleteReviewPayload:
    success: bool


@strawberry.type
class MarkReviewHelpfulPayload:
    helpfulCount: int
    viewerHasMarkedHelpful: bool


@strawberry.type
class ReportReviewPayload:
    success: bool


@strawberry.type
class ReplyToReviewPayload:
    review: ReviewType


@strawberry.type
class DeleteReviewReplyPayload:
    review: ReviewType
