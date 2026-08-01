import strawberry
from typing import List, Optional
from django.db.models import Q

from ..models.lost_found import CommunityQuestion, CommunityPoll, CommunityPollVote, QuestionView
from ..schema.community_schema import (
    CommunityQuestionType,
    CommunityPollType,
    PollCountsType,
    PollVoterType,
)


def _get_user(info):
    user = info.context.request.user
    return user if user.is_authenticated else None


@strawberry.type
class ViewSourcePoint:
    label: str
    value: float  # percent of total views


@strawberry.type
class ViewsOverTimePoint:
    date: str
    all: int
    followers: int
    nonFollowers: int


@strawberry.type
class QuestionViewAnalyticsType:
    totalViews: int
    sources: List[ViewSourcePoint]
    whoViewedFollowers: float
    whoViewedNonFollowers: float
    viewsOverTime: List[ViewsOverTimePoint]


def _empty_analytics() -> "QuestionViewAnalyticsType":
    return QuestionViewAnalyticsType(
        totalViews=0, sources=[], whoViewedFollowers=0.0, whoViewedNonFollowers=0.0, viewsOverTime=[]
    )


@strawberry.type
class QuestionEngagementType:
    views: int
    answers: int
    upvotes: int
    comments: int
    answerLikes: int
    interactions: int
    engagementRate: float  # capped at 100.0
    level: str  # High | Medium | Low


def _poll_qs_with_prefetch():
    """Return a queryset that prefetches options and votes to avoid N+1."""
    return CommunityPoll.objects.prefetch_related('poll_options', 'votes')


@strawberry.type
class CommunityQuery:

    @strawberry.field
    def community_questions(
        self,
        info: strawberry.types.Info,
        category: Optional[str] = None,
        sort: Optional[str] = "top",   # top | newest | unanswered | most_viewed
        filter: Optional[str] = None,  # mine
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[CommunityQuestionType]:
        user = _get_user(info)
        qs = CommunityQuestion.objects.all()

        # "Mine" tab — restrict to the authenticated user's questions
        if filter == "mine":
            qs = qs.filter(author=user) if user else qs.none()

        if category and category != "all":
            qs = qs.filter(category=category)

        if search and search.strip():
            qs = qs.filter(
                Q(title__icontains=search.strip()) | Q(body__icontains=search.strip())
            )

        if sort == "top":
            qs = qs.order_by("-score", "-created_at")
        elif sort == "unanswered":
            qs = qs.filter(answer_count=0).order_by("-created_at")
        elif sort == "most_viewed":
            qs = qs.order_by("-view_count", "-created_at")
        else:   # newest (default fallback)
            qs = qs.order_by("-created_at")

        return [CommunityQuestionType.from_model(q, user) for q in qs[offset: offset + limit]]

    @strawberry.field
    def community_question(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
        source: Optional[str] = None,
    ) -> Optional[CommunityQuestionType]:
        user = _get_user(info)
        try:
            q = CommunityQuestion.objects.prefetch_related("answers__likes").get(id=str(question_id))

            already_seen = False
            valid_sources = {"profile", "feed", "direct", "other"}
            view_source = source if source in valid_sources else "other"

            if user:
                # Author's own views never count.
                if q.author_id == user.pk:
                    already_seen = True
                else:
                    # DB-level dedup: unique_together (question, user) means
                    # get_or_create only inserts once; subsequent opens return
                    # created=False and we skip the increment.
                    from django.db import IntegrityError
                    try:
                        # Capture follower state at view time (real follow graph).
                        is_follower = False
                        if q.author_id:
                            from lipaidox.creator_profile.models.follow import Follow
                            is_follower = Follow.objects.filter(
                                follower=user, followed_id=q.author_id
                            ).exists()
                        _, created = QuestionView.objects.get_or_create(
                            question=q, user=user,
                            defaults={"source": view_source, "is_follower": is_follower},
                        )
                        already_seen = not created
                    except IntegrityError:
                        already_seen = True
            else:
                # Anonymous: fall back to Django session cookie.
                request = info.context.request
                session_key = f"viewed_q_{q.pk}"
                if request.session.get(session_key):
                    already_seen = True
                else:
                    request.session[session_key] = True

            if not already_seen:
                from django.db.models import F
                CommunityQuestion.objects.filter(pk=q.pk).update(view_count=F('view_count') + 1)
                q.view_count += 1

            return CommunityQuestionType.from_model(q, user, with_answers=True)
        except CommunityQuestion.DoesNotExist:
            return None

    @strawberry.field
    def question_view_analytics(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
    ) -> QuestionViewAnalyticsType:
        """Real view-source analytics for a question — author only."""
        from django.db.models import Count, Q as DQ
        from django.db.models.functions import TruncDate
        from django.utils import timezone
        from datetime import timedelta

        user = _get_user(info)
        if not user:
            return _empty_analytics()
        try:
            q = CommunityQuestion.objects.get(id=str(question_id))
        except CommunityQuestion.DoesNotExist:
            return _empty_analytics()
        # Insights are private to the question's author.
        if q.author_id != user.pk:
            return _empty_analytics()

        views = QuestionView.objects.filter(question=q)
        totals = views.aggregate(total=Count("id"), followers=Count("id", filter=DQ(is_follower=True)))
        total = totals["total"] or 0
        if total == 0:
            return _empty_analytics()

        def pct(n: int) -> float:
            return round((n / total) * 100, 1)

        # Top sources of views
        source_labels = {"profile": "Profile", "feed": "Feed", "direct": "Direct", "other": "Other"}
        source_rows = views.values("source").annotate(c=Count("id")).order_by("-c")
        sources = [
            ViewSourcePoint(label=source_labels.get(r["source"], r["source"].title()), value=pct(r["c"]))
            for r in source_rows
        ]

        # Who viewed (followers vs non-followers)
        followers = totals["followers"] or 0
        who_followers = pct(followers)
        who_non = round(100.0 - who_followers, 1)

        # Views over time — last 3 days, real daily counts
        start = (timezone.now() - timedelta(days=2)).date()
        by_day = {
            r["d"]: r
            for r in views.filter(viewed_at__date__gte=start)
            .annotate(d=TruncDate("viewed_at"))
            .values("d")
            .annotate(all=Count("id"), followers=Count("id", filter=DQ(is_follower=True)))
        }
        over_time = []
        for i in range(2, -1, -1):
            day = (timezone.now() - timedelta(days=i)).date()
            row = by_day.get(day)
            all_c = row["all"] if row else 0
            fol_c = row["followers"] if row else 0
            over_time.append(
                ViewsOverTimePoint(
                    date=day.strftime("%b %d"),
                    all=all_c,
                    followers=fol_c,
                    nonFollowers=all_c - fol_c,
                )
            )

        return QuestionViewAnalyticsType(
            totalViews=total,
            sources=sources,
            whoViewedFollowers=who_followers,
            whoViewedNonFollowers=who_non,
            viewsOverTime=over_time,
        )

    @strawberry.field
    def question_engagement(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
    ) -> QuestionEngagementType:
        """Real engagement aggregate for a question — author only, capped at 100%."""
        from ..models.lost_found import CommunityAnswer, CommunityAnswerLike

        empty = QuestionEngagementType(
            views=0, answers=0, upvotes=0, comments=0, answerLikes=0,
            interactions=0, engagementRate=0.0, level="Low",
        )
        user = _get_user(info)
        if not user:
            return empty
        try:
            q = CommunityQuestion.objects.get(id=str(question_id))
        except CommunityQuestion.DoesNotExist:
            return empty
        if q.author_id != user.pk:
            return empty

        answers = CommunityAnswer.objects.filter(question=q, parent__isnull=True).count()
        comments = CommunityAnswer.objects.filter(question=q, parent__isnull=False).count()
        answer_likes = CommunityAnswerLike.objects.filter(answer__question=q).count()
        upvotes = q.score or 0
        views = q.view_count or 0
        interactions = answers + comments + answer_likes + upvotes
        rate = min(100.0, round((interactions / views) * 100, 1)) if views > 0 else 0.0
        level = "High" if rate >= 30 else "Medium" if rate >= 10 else "Low"
        return QuestionEngagementType(
            views=views, answers=answers, upvotes=upvotes, comments=comments,
            answerLikes=answer_likes, interactions=interactions, engagementRate=rate, level=level,
        )

    @strawberry.field
    def trending_questions(
        self,
        info: strawberry.types.Info,
        limit: int = 5,
    ) -> List[CommunityQuestionType]:
        user = _get_user(info)
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        qs = (
            CommunityQuestion.objects
            .filter(created_at__gte=week_ago)
            .order_by("-answer_count", "-view_count")[:limit]
        )
        return [CommunityQuestionType.from_model(q, user) for q in qs]

    @strawberry.field
    def community_polls(
        self,
        info: strawberry.types.Info,
        filter: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[CommunityPollType]:
        from django.utils import timezone as tz
        user = _get_user(info)
        now = tz.now()
        qs = _poll_qs_with_prefetch()

        # Unpublished polls are only visible to their owner
        if user:
            qs = qs.filter(Q(is_published=True) | Q(author=user))
        else:
            qs = qs.filter(is_published=True)

        if filter == 'active':
            qs = qs.filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        elif filter == 'closed':
            qs = qs.filter(ends_at__lte=now)
        elif filter == 'mine':
            qs = qs.filter(author=user) if user else qs.none()
        elif filter == 'voted':
            qs = qs.filter(votes__user=user).distinct() if user else qs.none()

        return [CommunityPollType.from_model(p, user) for p in qs[offset: offset + limit]]

    @strawberry.field
    def poll_counts(self, info: strawberry.types.Info) -> PollCountsType:
        from django.utils import timezone as tz
        user = _get_user(info)
        now = tz.now()
        active = CommunityPoll.objects.filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).count()
        closed = CommunityPoll.objects.filter(ends_at__lte=now).count()
        mine   = CommunityPoll.objects.filter(author=user).count() if user else 0
        voted  = CommunityPoll.objects.filter(votes__user=user).distinct().count() if user else 0
        return PollCountsType(active=active, closed=closed, mine=mine, voted=voted)

    @strawberry.field
    def community_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> Optional[CommunityPollType]:
        user = _get_user(info)
        try:
            p = _poll_qs_with_prefetch().get(id=str(poll_id))
            # Count this detail open as an impression (atomic; reflect it in-memory).
            from django.db.models import F
            CommunityPoll.objects.filter(id=p.id).update(view_count=F('view_count') + 1)
            p.view_count = (p.view_count or 0) + 1
            return CommunityPollType.from_model(p, user)
        except CommunityPoll.DoesNotExist:
            return None

    @strawberry.field
    def poll_voters(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
        limit: int = 50,
    ) -> List[PollVoterType]:
        try:
            poll = CommunityPoll.objects.get(id=str(poll_id))
            if poll.is_anonymous:
                return []
            votes = (
                poll.votes
                .select_related("user", "option")
                .order_by("-created_at")[:limit]
            )
            return [PollVoterType.from_model(v) for v in votes]
        except CommunityPoll.DoesNotExist:
            return []
