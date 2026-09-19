"""GraphQL for app ratings: submit (any signed-in user) and review (admins)."""
from datetime import timedelta
from typing import List, Optional

import strawberry
from django.db.models import Avg, Count
from django.utils import timezone

from lipaidox.auth.permissions import UserRoles

from .models import AppFeedback

MAX_MESSAGE_LENGTH = 2000
#: Enough for someone who changes their mind; too few to flood the inbox.
MAX_SUBMISSIONS_PER_DAY = 5


def _user(info):
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise Exception("Sign in to send feedback.")
    return user


def _admin(info):
    user = _user(info)
    if user.role not in [UserRoles.ADMIN, "superadmin"]:
        raise Exception("Admin access required")
    return user


@strawberry.type
class SubmitFeedbackResult:
    success: bool
    message: str


@strawberry.type
class AppFeedbackType:
    id: strawberry.ID
    userId: Optional[strawberry.ID]
    username: Optional[str]
    rating: int
    message: str
    appVersion: str
    platform: str
    createdAt: str

    @classmethod
    def from_model(cls, f: AppFeedback) -> "AppFeedbackType":
        return cls(
            id=strawberry.ID(str(f.id)),
            userId=strawberry.ID(str(f.user_id)) if f.user_id else None,
            username=f.user.username if f.user_id else None,
            rating=f.rating, message=f.message, appVersion=f.app_version, platform=f.platform,
            createdAt=f.created_at.isoformat(),
        )


@strawberry.type
class RatingBucket:
    stars: int
    count: int


@strawberry.type
class AppFeedbackSummary:
    total: int
    average: float
    distribution: List[RatingBucket]


@strawberry.type
class FeedbackMutation:
    @strawberry.mutation
    def submit_app_feedback(
        self,
        info: strawberry.types.Info,
        rating: int,
        message: Optional[str] = None,
        appVersion: Optional[str] = None,
        platform: Optional[str] = None,
        appId: Optional[str] = None,
    ) -> SubmitFeedbackResult:
        """Record a 1–5 star rating with an optional comment. Throttled per user per day."""
        user = _user(info)
        if not 1 <= int(rating) <= 5:
            raise Exception("Rating must be between 1 and 5 stars.")
        text = (message or "").strip()
        if len(text) > MAX_MESSAGE_LENGTH:
            raise Exception(f"Please keep feedback under {MAX_MESSAGE_LENGTH} characters.")

        since = timezone.now() - timedelta(days=1)
        if AppFeedback.objects.filter(user=user, created_at__gte=since).count() >= MAX_SUBMISSIONS_PER_DAY:
            raise Exception("You've sent a lot of feedback today. Please try again tomorrow.")

        AppFeedback.objects.create(
            user=user, rating=int(rating), message=text,
            app_version=(appVersion or "")[:30], platform=(platform or "")[:40], app_id=(appId or "")[:120],
        )
        return SubmitFeedbackResult(success=True, message="Thanks for your feedback!")


@strawberry.type
class FeedbackQuery:
    @strawberry.field
    def admin_app_feedback(
        self,
        info: strawberry.types.Info,
        maxRating: Optional[int] = None,
        minRating: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AppFeedbackType]:
        """Feedback newest first; filter to e.g. `maxRating: 3` to triage complaints."""
        _admin(info)
        limit = max(1, min(int(limit), 100))
        qs = AppFeedback.objects.select_related("user")
        if maxRating is not None:
            qs = qs.filter(rating__lte=maxRating)
        if minRating is not None:
            qs = qs.filter(rating__gte=minRating)
        return [AppFeedbackType.from_model(f) for f in qs[max(0, offset): max(0, offset) + limit]]

    @strawberry.field
    def admin_app_feedback_summary(self, info: strawberry.types.Info) -> AppFeedbackSummary:
        _admin(info)
        agg = AppFeedback.objects.aggregate(total=Count("id"), avg=Avg("rating"))
        counts = {r["rating"]: r["n"] for r in AppFeedback.objects.values("rating").annotate(n=Count("id"))}
        return AppFeedbackSummary(
            total=agg["total"] or 0,
            average=round(float(agg["avg"] or 0), 2),
            distribution=[RatingBucket(stars=s, count=counts.get(s, 0)) for s in (5, 4, 3, 2, 1)],
        )
