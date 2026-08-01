"""
Real, computed-on-demand per-content insights.

Every number here is aggregated from actual rows — UserInteraction events
(views/likes/shares/saves with watch duration, completion, source), the Content
counters, ContentReview ratings, and MembershipSubscription for the subscriber
split. Nothing is fabricated; fields with no events simply return 0. Analytics
accrue as interactions are recorded going forward.
"""
import strawberry
from typing import List, Optional
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from ..models import Content
from lipaidox.auth.permissions import require_creator


@strawberry.type
class InsightPointType:
    label: str
    value: int


def _content_thumbnail(content) -> Optional[str]:
    """Best available thumbnail: a media thumbnail, else an image file, else any media file."""
    media = list(content.media.all())
    for m in media:
        if getattr(m, "thumbnail_url", None):
            return m.thumbnail_url
    for m in media:
        if getattr(m, "media_type", None) == "image" and m.file_url:
            return m.file_url
    return media[0].file_url if media else None


@strawberry.type
class ContentInsightsType:
    id: strawberry.ID
    title: str
    thumbnail_url: Optional[str]
    # Header interaction counts (real)
    views: int
    unique_views: int
    likes: int
    comments: int
    shares: int
    saves: int
    purchases: int
    # Reviews (real)
    review_count: int
    average_rating: float
    # Engagement quality (real)
    average_watch_time_seconds: int
    average_completion_rate: float  # 0..1
    engagement_rate: float          # (likes+comments+shares+saves)/views, 0..1
    # Audience split (real, from active memberships)
    subscriber_views: int
    non_subscriber_views: int
    # Time series + sources (real)
    views_over_time: List[InsightPointType]
    view_sources: List[InsightPointType]


@strawberry.type
class ContentInsightsQuery:
    @strawberry.field
    @require_creator
    def content_insights(
        self, info: strawberry.types.Info, content_id: strawberry.ID
    ) -> Optional[ContentInsightsType]:
        user = info.context.request.user
        try:
            content = Content.objects.select_related("creator").get(
                id=content_id, creator__user=user
            )
        except Content.DoesNotExist:
            return None

        from lipaidox.recommendation.models.user_interactions import (
            UserInteraction,
            InteractionType,
        )
        from lipaidox.content.models.content_review import ContentReview

        inter = UserInteraction.objects.filter(content=content)
        views_qs = inter.filter(interaction_type=InteractionType.VIEW)

        tracked_views = views_qs.count()
        total_views = max(content.view_count or 0, tracked_views)
        unique_views = (
            views_qs.exclude(user__isnull=True).values("user").distinct().count()
        )
        likes = content.like_count or inter.filter(
            interaction_type=InteractionType.LIKE
        ).count()
        comments = content.comment_count or inter.filter(
            interaction_type=InteractionType.COMMENT
        ).count()
        shares = inter.filter(interaction_type=InteractionType.SHARE).count()
        saves = inter.filter(interaction_type=InteractionType.SAVE).count()
        purchases = content.purchase_count or 0

        agg = views_qs.aggregate(w=Avg("watch_duration_s"), c=Avg("completion_rate"))
        avg_watch = int(agg["w"] or 0)
        avg_completion = float(agg["c"] or 0)

        reviews = ContentReview.objects.filter(content=content, status="published")
        review_count = reviews.count()
        average_rating = float(reviews.aggregate(a=Avg("rating"))["a"] or 0)

        # Subscriber vs non-subscriber views (based on current active memberships).
        subscriber_views = 0
        non_subscriber_views = 0
        try:
            from lipaidox.creator_profile.models.membership import MembershipSubscription

            sub_ids = set(
                MembershipSubscription.objects.filter(
                    target=content.creator, status="active"
                ).values_list("subscriber_id", flat=True)
            )
            for uid in views_qs.exclude(user__isnull=True).values_list(
                "user_id", flat=True
            ):
                if uid in sub_ids:
                    subscriber_views += 1
                else:
                    non_subscriber_views += 1
        except Exception:
            pass

        interactions_total = likes + comments + shares + saves
        engagement_rate = (
            round(interactions_total / total_views, 4) if total_views else 0.0
        )

        # Views over time — last 14 days, one point per day (real counts).
        since = timezone.now() - timedelta(days=13)
        by_day: dict[str, int] = {}
        for dt in views_qs.filter(interacted_at__gte=since).values_list(
            "interacted_at", flat=True
        ):
            key = dt.date().isoformat()
            by_day[key] = by_day.get(key, 0) + 1
        views_over_time = [
            InsightPointType(
                label=(since + timedelta(days=i)).date().isoformat(),
                value=by_day.get((since + timedelta(days=i)).date().isoformat(), 0),
            )
            for i in range(14)
        ]

        # Top sources of views (real, grouped by the source captured at view time).
        source_rows = (
            views_qs.values("source").annotate(n=Count("id")).order_by("-n")
        )
        view_sources = [
            InsightPointType(label=(r["source"] or "other"), value=r["n"])
            for r in source_rows
            if r["n"] > 0
        ]

        return ContentInsightsType(
            id=strawberry.ID(str(content.id)),
            title=content.title,
            thumbnail_url=_content_thumbnail(content),
            views=total_views,
            unique_views=unique_views,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            purchases=purchases,
            review_count=review_count,
            average_rating=round(average_rating, 2),
            average_watch_time_seconds=avg_watch,
            average_completion_rate=round(avg_completion, 4),
            engagement_rate=engagement_rate,
            subscriber_views=subscriber_views,
            non_subscriber_views=non_subscriber_views,
            views_over_time=views_over_time,
            view_sources=view_sources,
        )
