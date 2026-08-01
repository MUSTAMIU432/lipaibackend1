import strawberry
from typing import Optional
from datetime import datetime


@strawberry.type
class ContentReviewAuthorType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool


@strawberry.type
class ContentReviewOwnerReplyType:
    body: str
    createdAt: datetime
    editedAt: Optional[datetime]


@strawberry.type
class ContentReviewType:
    id: strawberry.ID
    author: ContentReviewAuthorType
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
    ownerReply: Optional[ContentReviewOwnerReplyType] = None


@strawberry.type
class ContentReviewListType:
    items: list[ContentReviewType]
    totalCount: int


@strawberry.type
class ContentRatingDistributionType:
    oneStar: int
    twoStar: int
    threeStar: int
    fourStar: int
    fiveStar: int


@strawberry.type
class ContentReviewSummaryType:
    averageRating: float
    totalReviews: int
    verifiedReviews: int
    ratingDistribution: ContentRatingDistributionType


@strawberry.type
class ContentReviewEligibilityType:
    canReview: bool
    hasReviewed: bool
    reason: Optional[str] = None


@strawberry.type
class CreateContentReviewPayload:
    review: ContentReviewType


@strawberry.type
class UpdateContentReviewPayload:
    review: ContentReviewType


@strawberry.type
class DeleteContentReviewPayload:
    success: bool


@strawberry.type
class MarkContentReviewHelpfulPayload:
    helpfulCount: int
    viewerHasMarkedHelpful: bool


@strawberry.type
class ReportContentReviewPayload:
    success: bool


@strawberry.type
class ReplyToContentReviewPayload:
    review: ContentReviewType


@strawberry.type
class DeleteContentReviewReplyPayload:
    review: ContentReviewType
