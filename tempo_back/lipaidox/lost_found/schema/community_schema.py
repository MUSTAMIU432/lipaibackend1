import strawberry
from typing import Optional, List, Union, Annotated
from datetime import datetime

from ..models.lost_found import (
    CommunityQuestion,
    CommunityAnswer,
    CommunityPoll,
    PollOption,
    CommunityPollVote,
    QuestionVote,
)

# ─── Vote-change anti-gaming constants ────────────────────────────────────────
# These are authoritative server-side values.  The frontend may read them from
# viewerChangesRemaining / viewerCanChange but must never skip the server checks.
VOTE_CHANGE_MAX = 3                  # max times a user may change their vote per poll
VOTE_CHANGE_COOLDOWN_SECONDS = 30    # minimum seconds between consecutive changes
VOTE_CHANGE_LOCK_IN_MINUTES = 5      # no changes allowed this close to poll close


def _author_avatar(author) -> Optional[str]:
    """Profile photo URL for a community author, or None if unavailable."""
    if author is None:
        return None
    try:
        profile = author.profile
    except Exception:
        return None
    return getattr(profile, "profile_photo_url", None)


def _compute_option_percents(vote_counts: list, total_votes: int, is_multiple: bool) -> list:
    """
    Exact Python port of lib/poll-percent.ts :: computeOptionPercents().
    Returns one display-ready INTEGER percent per option (same order).

    Zero-vote guard : total_votes == 0 → all zeros, no division.
    Single-choice   : Hamilton / largest-remainder rounding.
                      Integer percents always sum to exactly 100.
    Multiple-choice : each option rounded independently with round().
                      Sum intentionally exceeds 100 (options are not
                      mutually exclusive slices of a pie).

    BAR WIDTH == returned percent.  Use the same number for both the
    label and the bar width so they can never disagree.
    """
    n = len(vote_counts)
    if total_votes == 0 or n == 0:
        return [0] * n

    if is_multiple:
        # Each option: voteCount / distinctVoters × 100, independent rounding.
        # Do NOT apply largest-remainder — options are not mutually exclusive.
        return [round(vc / total_votes * 100) for vc in vote_counts]

    # Single-choice: Hamilton / largest-remainder.
    # Step 1 – raw floats (never round until the final step).
    raw = [vc / total_votes * 100 for vc in vote_counts]
    # Step 2 – floor each value.
    floors = [int(r) for r in raw]
    # Step 3 – how many +1 units remain?
    remainder = 100 - sum(floors)
    # Step 4 – give +1 to options with the largest fractional parts
    #           (ties broken by original index for stability).
    fracs = sorted(range(n), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in fracs[:remainder]:
        floors[i] += 1
    return floors


# ─── Output Types ─────────────────────────────────────────────────────────────

@strawberry.type
class CommunityAnswerType:
    id: strawberry.ID
    body: str
    author_name: str
    author_avatar: Optional[str]
    like_count: int
    liked_by_me: bool
    created_at: datetime
    parent_id: Optional[strawberry.ID]

    @classmethod
    def from_model(cls, instance: CommunityAnswer, user=None) -> "CommunityAnswerType":
        liked = False
        if user and user.is_authenticated:
            liked = instance.likes.filter(user=user).exists()
        author = instance.author
        return cls(
            id=strawberry.ID(str(instance.id)),
            body=instance.body,
            author_name=author.username if author else "Anonymous",
            author_avatar=_author_avatar(author),
            like_count=instance.like_count,
            liked_by_me=liked,
            created_at=instance.created_at,
            parent_id=strawberry.ID(str(instance.parent_id)) if instance.parent_id else None,
        )


@strawberry.type
class CommunityQuestionType:
    id: strawberry.ID
    title: str
    body: str
    category: str
    image_url: str
    author_name: str
    author_avatar: Optional[str]
    view_count: int
    answer_count: int
    share_count: int
    score: int
    viewer_vote: bool       # True when the authenticated user has upvoted this question
    is_owner: bool          # True when the authenticated user is the author
    created_at: datetime
    answers: Optional[List[CommunityAnswerType]] = None

    @classmethod
    def from_model(cls, instance: CommunityQuestion, user=None, with_answers: bool = False) -> "CommunityQuestionType":
        author = instance.author
        answers = None
        if with_answers:
            answers = [CommunityAnswerType.from_model(a, user) for a in instance.answers.all()]

        viewer_vote = False
        is_owner = False
        if user and user.is_authenticated:
            viewer_vote = instance.votes.filter(user=user).exists()
            is_owner = (
                instance.author_id is not None
                and str(instance.author_id) == str(user.pk)
            )

        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            body=instance.body,
            category=instance.category,
            image_url=instance.image_url,
            author_name=author.username if author else "Anonymous",
            author_avatar=_author_avatar(author),
            view_count=instance.view_count,
            answer_count=instance.answer_count,
            share_count=getattr(instance, 'share_count', 0) or 0,
            score=instance.score,
            viewer_vote=viewer_vote,
            is_owner=is_owner,
            created_at=instance.created_at,
            answers=answers,
        )


@strawberry.type
class PollOptionType:
    id: strawberry.ID
    text: str
    vote_count: int
    # Integer percent from _compute_option_percents — never a stored column.
    # Always computed at read time; bar width == this value.
    percent: int
    order: int

    @classmethod
    def from_model(cls, instance: PollOption, percent: int) -> "PollOptionType":
        """
        percent must be pre-computed by _compute_option_percents() at the poll
        level (so Hamilton rounding can see all options at once).
        """
        return cls(
            id=strawberry.ID(str(instance.id)),
            text=instance.text,
            vote_count=instance.vote_count,
            percent=percent,
            order=instance.order,
        )


@strawberry.type
class PollVoterType:
    voter_name: str
    voter_avatar: Optional[str]
    option_text: str
    voted_at: datetime

    @classmethod
    def from_model(cls, instance: CommunityPollVote) -> "PollVoterType":
        user = instance.user
        opt_text = instance.option.text if instance.option else "Unknown"
        return cls(
            voter_name=user.username if user else "Anonymous",
            voter_avatar=_author_avatar(user),
            option_text=opt_text,
            voted_at=instance.created_at,
        )


@strawberry.type
class PollCountsType:
    active: int
    closed: int
    mine: int
    voted: int


@strawberry.type
class CommunityPollType:
    id: strawberry.ID
    question: str
    options: List[PollOptionType]
    total_votes: int
    view_count: int
    share_count: int
    days_left: int
    ends_at: Optional[datetime]
    status: str
    is_anonymous: bool
    poll_type: str
    max_selections: Optional[int]
    verified_only: bool
    hide_results_until_close: bool
    allow_vote_change: bool
    allow_write_in: bool
    allow_comments: bool
    tags: List[str]
    user_voted_option: Optional[strawberry.ID]
    is_owner: bool
    is_published: bool
    created_at: datetime
    author_name: str
    author_avatar: Optional[str]
    # Viewer-specific change-vote state (False / 0 for unauthenticated users)
    viewer_can_change: bool
    viewer_changes_remaining: int

    @classmethod
    def from_model(cls, instance: CommunityPoll, user=None) -> "CommunityPollType":
        from django.utils import timezone
        now = timezone.now()
        total = instance.total_votes or 0
        is_multiple = getattr(instance, 'poll_type', 'single') == 'multiple'

        # Compute percents once for ALL options so Hamilton rounding can
        # see every fractional part and guarantee the sum == 100.
        option_instances = list(instance.poll_options.all())
        vote_counts = [opt.vote_count for opt in option_instances]
        percents = _compute_option_percents(vote_counts, total, is_multiple)
        options_result = [
            PollOptionType.from_model(opt, pct)
            for opt, pct in zip(option_instances, percents)
        ]

        days_left = 0
        status = 'active'
        if instance.ends_at:
            delta = instance.ends_at - now
            if delta.total_seconds() <= 0:
                status = 'closed'
            else:
                days_left = max(0, delta.days)

        voted_option_id = None
        is_owner_flag = False
        viewer_can_change = False
        viewer_changes_remaining = VOTE_CHANGE_MAX
        vote_obj = None  # reused for change-tracking below

        if user and user.is_authenticated:
            vote_obj = instance.votes.filter(user=user).select_related('option').first()
            if vote_obj and vote_obj.option:
                voted_option_id = strawberry.ID(str(vote_obj.option_id))
            if instance.author_id is not None:
                is_owner_flag = str(instance.author_id) == str(user.pk)

        # ── viewerCanChange ────────────────────────────────────────────────────
        # All conditions must hold:
        #  1. poll has allow_vote_change enabled
        #  2. poll is currently active (not closed)
        #  3. not inside the lock-in window before close
        #  4. the user has already voted (so there is a row to UPDATE)
        #  5. changes remaining (change_count < MAX)
        #  6. cooldown elapsed since last change
        allow_vote_change_flag = getattr(instance, 'allow_vote_change', True)
        if (
            user and user.is_authenticated
            and allow_vote_change_flag
            and status == 'active'
            and voted_option_id is not None
            and vote_obj is not None
        ):
            # Check lock-in window
            in_lockout = (
                instance.ends_at is not None
                and (instance.ends_at - now).total_seconds()
                   <= VOTE_CHANGE_LOCK_IN_MINUTES * 60
            )
            if not in_lockout:
                remaining = VOTE_CHANGE_MAX - (vote_obj.change_count or 0)
                viewer_changes_remaining = max(0, remaining)
                if remaining > 0:
                    # Check cooldown: no previous change, or cooldown elapsed
                    last = vote_obj.last_changed_at
                    cooldown_ok = (
                        last is None
                        or (now - last).total_seconds() >= VOTE_CHANGE_COOLDOWN_SECONDS
                    )
                    viewer_can_change = cooldown_ok
            else:
                viewer_changes_remaining = max(
                    0, VOTE_CHANGE_MAX - (vote_obj.change_count or 0)
                )

        author = instance.author
        return cls(
            id=strawberry.ID(str(instance.id)),
            question=instance.question,
            options=options_result,
            total_votes=total,
            view_count=getattr(instance, 'view_count', 0) or 0,
            share_count=getattr(instance, 'share_count', 0) or 0,
            days_left=days_left,
            ends_at=instance.ends_at,
            status=status,
            is_anonymous=instance.is_anonymous,
            poll_type=getattr(instance, 'poll_type', 'single'),
            max_selections=getattr(instance, 'max_selections', None),
            verified_only=getattr(instance, 'verified_only', False),
            hide_results_until_close=getattr(instance, 'hide_results_until_close', False),
            allow_vote_change=allow_vote_change_flag,
            allow_write_in=getattr(instance, 'allow_write_in', False),
            allow_comments=getattr(instance, 'allow_comments', True),
            tags=getattr(instance, 'tags', []) or [],
            user_voted_option=voted_option_id,
            is_owner=is_owner_flag,
            created_at=instance.created_at,
            author_name=author.username if author else "Anonymous",
            author_avatar=_author_avatar(author) if author else None,
            is_published=getattr(instance, 'is_published', True),
            viewer_can_change=viewer_can_change,
            viewer_changes_remaining=viewer_changes_remaining,
        )


# ─── castVote result union ─────────────────────────────────────────────────────

@strawberry.type
class CastVoteError:
    """Returned instead of a 500 when vote is rejected for a known reason."""
    code: str          # ALREADY_VOTED | POLL_CLOSED | NOT_VERIFIED | INVALID_OPTION
    message: str
    user_vote: Optional[strawberry.ID] = None  # set on ALREADY_VOTED


CastVoteResult = strawberry.union(
    "CastVoteResult",
    types=(CommunityPollType, CastVoteError),
)


# ─── changeVote result union ───────────────────────────────────────────────────

@strawberry.type
class ChangeVoteError:
    """
    Returned instead of a 500 when a vote-change is rejected.
    All codes are machine-readable so the frontend can show precise feedback.
    """
    code: str
    # Possible codes:
    #   CHANGE_DISABLED      — allow_vote_change=False on this poll
    #   CHANGE_LIMIT_REACHED — user exhausted their MAX_VOTE_CHANGES changes
    #   CHANGE_TOO_SOON      — cooldown between changes not elapsed
    #   CHANGE_WINDOW_CLOSED — within LOCK_IN_BEFORE_CLOSE_MINUTES of close time
    #   POLL_CLOSED          — poll has ended
    #   NOT_VOTED            — user has no vote to change yet
    #   INVALID_OPTION       — new_option_id not on this poll
    message: str


ChangeVoteResult = strawberry.union(
    "ChangeVoteResult",
    types=(CommunityPollType, ChangeVoteError),
)


# ─── Input Types ──────────────────────────────────────────────────────────────

@strawberry.input
class CreateQuestionInput:
    title: str
    category: str = "general"
    body: Optional[str] = None
    image_url: Optional[str] = None


@strawberry.input
class CreatePollInput:
    question: str
    options: List[str]
    duration_days: int = 3
    is_anonymous: bool = True
    poll_type: str = 'single'
    max_selections: Optional[int] = None
    closes_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    verified_only: bool = False
    hide_results_until_close: bool = False
    allow_vote_change: bool = True   # ignored (forced False) when verified_only or hide_results_until_close
    allow_write_in: bool = False
    allow_comments: bool = True


@strawberry.input
class UpdatePollInput:
    question: Optional[str] = None
    tags: Optional[List[str]] = None
    options: Optional[List[str]] = None   # only honoured when total_votes == 0
    duration_days: Optional[int] = None   # extends ends_at from now


# ─── Minimal success types ────────────────────────────────────────────────────

@strawberry.type
class LikeToggleResult:
    liked: bool
    like_count: int
