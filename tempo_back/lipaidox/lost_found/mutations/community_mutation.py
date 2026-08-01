import strawberry
from typing import Optional
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta

from django.db.models import F

from ..models.lost_found import (
    CommunityQuestion,
    CommunityAnswer,
    CommunityAnswerLike,
    QuestionVote,
    CommunityPoll,
    PollOption,
    CommunityPollVote,
    VoteChange,
)
from ..schema.community_schema import (
    CommunityQuestionType,
    CommunityAnswerType,
    CommunityPollType,
    CastVoteError,
    CastVoteResult,
    ChangeVoteError,
    ChangeVoteResult,
    LikeToggleResult,
    CreateQuestionInput,
    CreatePollInput,
    UpdatePollInput,
    VOTE_CHANGE_MAX,
    VOTE_CHANGE_COOLDOWN_SECONDS,
    VOTE_CHANGE_LOCK_IN_MINUTES,
)


def require_auth(info):
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


@strawberry.type
class CommunityMutation:

    # ── World Ask ────────────────────────────────────────────────────────────

    @strawberry.mutation
    def create_community_question(
        self,
        info: strawberry.types.Info,
        input: CreateQuestionInput,
    ) -> CommunityQuestionType:
        user = require_auth(info)
        clean_title = input.title.strip()
        if len(clean_title) < 10:
            raise Exception("Title must be at least 10 characters")
        q = CommunityQuestion.objects.create(
            author=user,
            title=clean_title,
            body=(input.body or "").strip(),
            category=input.category or "general",
            image_url=(input.image_url or "").strip(),
        )
        return CommunityQuestionType.from_model(q, user)

    @strawberry.mutation
    def delete_community_question(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
    ) -> bool:
        user = require_auth(info)
        try:
            q = CommunityQuestion.objects.get(id=str(question_id))
        except CommunityQuestion.DoesNotExist:
            return False
        if str(q.author_id) != str(user.pk):
            raise Exception("You can only delete your own questions")
        q.delete()
        return True

    @strawberry.mutation
    def upvote_question(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
    ) -> CommunityQuestionType:
        """
        Toggle an upvote on a question.  First call adds the vote and increments
        score; calling again removes it and decrements score.  Enforces exactly
        one vote per user via get_or_create + IntegrityError backstop (same
        pattern as cast_vote on polls).
        """
        user = require_auth(info)
        try:
            question = CommunityQuestion.objects.get(id=str(question_id))
        except CommunityQuestion.DoesNotExist:
            raise Exception("Question not found")

        try:
            with transaction.atomic():
                vote, created = QuestionVote.objects.get_or_create(
                    question=question,
                    user=user,
                )
                if created:
                    # New vote — increment score atomically
                    CommunityQuestion.objects.filter(pk=question.pk).update(score=F('score') + 1)
                else:
                    # Already voted — toggle off, decrement score
                    vote.delete()
                    CommunityQuestion.objects.filter(pk=question.pk).update(score=F('score') - 1)
        except IntegrityError:
            # Race-condition backstop: concurrent request already inserted the row.
            # State is consistent; just fall through and return current state.
            pass

        question.refresh_from_db()
        return CommunityQuestionType.from_model(question, user)

    @strawberry.mutation
    def post_community_answer(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
        body: str,
        parent_id: Optional[strawberry.ID] = None,
    ) -> CommunityAnswerType:
        user = require_auth(info)
        try:
            question = CommunityQuestion.objects.get(id=str(question_id))
        except CommunityQuestion.DoesNotExist:
            raise Exception("Question not found")

        parent = None
        if parent_id:
            try:
                parent = CommunityAnswer.objects.get(id=str(parent_id), question=question)
            except CommunityAnswer.DoesNotExist:
                raise Exception("Parent answer not found")

        with transaction.atomic():
            answer = CommunityAnswer.objects.create(
                question=question,
                parent=parent,
                author=user,
                body=body.strip(),
            )
            # Only top-level answers count toward the question's answer_count.
            if parent is None:
                CommunityQuestion.objects.filter(pk=question.pk).update(
                    answer_count=F('answer_count') + 1
                )

        return CommunityAnswerType.from_model(answer, user)

    @strawberry.mutation
    def toggle_answer_like(
        self,
        info: strawberry.types.Info,
        answer_id: strawberry.ID,
    ) -> LikeToggleResult:
        user = require_auth(info)
        try:
            answer = CommunityAnswer.objects.get(id=str(answer_id))
        except CommunityAnswer.DoesNotExist:
            raise Exception("Answer not found")

        with transaction.atomic():
            like, created = CommunityAnswerLike.objects.get_or_create(answer=answer, user=user)
            if created:
                CommunityAnswer.objects.filter(pk=answer.pk).update(like_count=answer.like_count + 1)
                return LikeToggleResult(liked=True, like_count=answer.like_count + 1)
            else:
                like.delete()
                new_count = max(0, answer.like_count - 1)
                CommunityAnswer.objects.filter(pk=answer.pk).update(like_count=new_count)
                return LikeToggleResult(liked=False, like_count=new_count)

    @strawberry.mutation
    def record_question_share(
        self,
        info: strawberry.types.Info,
        question_id: strawberry.ID,
    ) -> int:
        """Increment an Ask/question's share counter. Returns the new total."""
        from django.db.models import F
        updated = CommunityQuestion.objects.filter(id=str(question_id)).update(
            share_count=F('share_count') + 1
        )
        if not updated:
            return 0
        return CommunityQuestion.objects.only('share_count').get(id=str(question_id)).share_count

    # ── Polls ────────────────────────────────────────────────────────────────

    @strawberry.mutation
    def record_poll_share(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> int:
        """Increment a poll's share counter (any viewer). Returns the new total."""
        from django.db.models import F
        updated = CommunityPoll.objects.filter(id=str(poll_id)).update(
            share_count=F('share_count') + 1
        )
        if not updated:
            return 0
        return CommunityPoll.objects.only('share_count').get(id=str(poll_id)).share_count

    @strawberry.mutation
    def create_community_poll(
        self,
        info: strawberry.types.Info,
        input: CreatePollInput,
    ) -> CommunityPollType:
        user = require_auth(info)

        clean_options = [o.strip() for o in input.options if o.strip()]
        if len(clean_options) < 2:
            raise Exception("A poll requires at least 2 options")
        if len(clean_options) > 6:
            raise Exception("A poll allows at most 6 options")

        now = timezone.now()
        ends_at = input.closes_at if input.closes_at is not None else now + timedelta(days=input.duration_days)

        with transaction.atomic():
            poll = CommunityPoll.objects.create(
                author=user,
                question=input.question.strip(),
                poll_type=input.poll_type or 'single',
                max_selections=input.max_selections,
                duration_days=input.duration_days,
                is_anonymous=input.is_anonymous,
                verified_only=input.verified_only,
                hide_results_until_close=input.hide_results_until_close,
                # Model.save() overrides this to False when verified_only or
                # hide_results_until_close is True, so no need for manual guard here.
                allow_vote_change=getattr(input, 'allow_vote_change', True),
                allow_write_in=input.allow_write_in,
                allow_comments=input.allow_comments,
                tags=input.tags or [],
                ends_at=ends_at,
            )
            PollOption.objects.bulk_create([
                PollOption(poll=poll, text=text, order=i, vote_count=0)
                for i, text in enumerate(clean_options)
            ])

        poll.poll_options.all()  # warm the cached queryset
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def cast_vote(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
        option_id: strawberry.ID,
    ) -> CastVoteResult:
        """
        Cast one vote.  Returns the updated CommunityPollType on success, or a
        CastVoteError with a machine-readable code on any known rejection:
          POLL_CLOSED    — poll has ended
          NOT_VERIFIED   — poll.verified_only and user is not verified
          ALREADY_VOTED  — user already has a vote on this poll
          INVALID_OPTION — option_id does not belong to this poll
        """
        user = require_auth(info)

        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")

        # ── Guard: closed ────────────────────────────────────────────────────
        now = timezone.now()
        if poll.ends_at and poll.ends_at <= now:
            return CastVoteError(
                code="POLL_CLOSED",
                message="This poll has ended and is no longer accepting votes.",
            )

        # ── Guard: verified_only ─────────────────────────────────────────────
        if poll.verified_only:
            is_verified = getattr(user, 'is_verified', False)
            if not is_verified:
                # Also check profile field as fallback
                try:
                    profile = user.profile
                    is_verified = getattr(profile, 'is_verified', False) or getattr(profile, 'kyc_verified', False)
                except Exception:
                    pass
            if not is_verified:
                return CastVoteError(
                    code="NOT_VERIFIED",
                    message="Only verified users can vote on this poll.",
                )

        # ── Guard: option belongs to this poll ───────────────────────────────
        try:
            option = poll.poll_options.get(id=str(option_id))
        except PollOption.DoesNotExist:
            return CastVoteError(
                code="INVALID_OPTION",
                message="That option does not exist on this poll.",
            )

        # ── Cast vote inside a transaction ───────────────────────────────────
        try:
            with transaction.atomic():
                _, created = CommunityPollVote.objects.get_or_create(
                    poll=poll,
                    user=user,
                    defaults={'option': option},
                )

                if not created:
                    # User already voted — return their existing choice
                    existing = CommunityPollVote.objects.filter(
                        poll=poll, user=user
                    ).select_related('option').first()
                    existing_id = (
                        strawberry.ID(str(existing.option_id))
                        if existing and existing.option_id else None
                    )
                    return CastVoteError(
                        code="ALREADY_VOTED",
                        message="You have already voted on this poll.",
                        user_vote=existing_id,
                    )

                # Increment counters atomically
                PollOption.objects.filter(pk=option.pk).update(
                    vote_count=option.vote_count + 1
                )
                CommunityPoll.objects.filter(pk=poll.pk).update(
                    total_votes=poll.total_votes + 1
                )

        except IntegrityError:
            # Race-condition backstop: another request won the unique constraint
            existing = CommunityPollVote.objects.filter(
                poll=poll, user=user
            ).select_related('option').first()
            existing_id = (
                strawberry.ID(str(existing.option_id))
                if existing and existing.option_id else None
            )
            return CastVoteError(
                code="ALREADY_VOTED",
                message="You have already voted on this poll.",
                user_vote=existing_id,
            )

        # Re-fetch for fresh counts
        poll.refresh_from_db()
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def close_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> CommunityPollType:
        user = require_auth(info)
        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")
        if poll.author_id is None or str(poll.author_id) != str(user.pk):
            raise Exception("You don't own this poll")
        now = timezone.now()
        CommunityPoll.objects.filter(pk=poll.pk).update(ends_at=now)
        poll.ends_at = now
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def delete_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> bool:
        user = require_auth(info)
        try:
            poll = CommunityPoll.objects.get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")
        if poll.author_id is None or str(poll.author_id) != str(user.pk):
            raise Exception("You don't own this poll")
        poll.delete()
        return True

    @strawberry.mutation
    def unpublish_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> CommunityPollType:
        user = require_auth(info)
        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")
        if poll.author_id is None or str(poll.author_id) != str(user.pk):
            raise Exception("You don't own this poll")
        CommunityPoll.objects.filter(pk=poll.pk).update(is_published=False)
        poll.is_published = False
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def republish_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
    ) -> CommunityPollType:
        user = require_auth(info)
        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")
        if poll.author_id is None or str(poll.author_id) != str(user.pk):
            raise Exception("You don't own this poll")
        CommunityPoll.objects.filter(pk=poll.pk).update(is_published=True)
        poll.is_published = True
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def update_poll(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
        input: UpdatePollInput,
    ) -> CommunityPollType:
        user = require_auth(info)
        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(id=str(poll_id))
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")
        if poll.author_id is None or str(poll.author_id) != str(user.pk):
            raise Exception("You don't own this poll")

        updates = {}
        if input.question is not None:
            q = input.question.strip()
            if not q:
                raise Exception("Question cannot be empty")
            updates['question'] = q
        if input.tags is not None:
            updates['tags'] = input.tags
        if input.duration_days is not None:
            updates['ends_at'] = timezone.now() + timedelta(days=input.duration_days)

        with transaction.atomic():
            if updates:
                CommunityPoll.objects.filter(pk=poll.pk).update(**updates)
                for k, v in updates.items():
                    setattr(poll, k, v)

            # Options can only be replaced when no votes have been cast yet
            if input.options is not None:
                if poll.total_votes > 0:
                    raise Exception("Options cannot be changed after votes have been cast")
                clean = [o.strip() for o in input.options if o.strip()]
                if len(clean) < 2:
                    raise Exception("A poll requires at least 2 options")
                if len(clean) > 6:
                    raise Exception("A poll allows at most 6 options")
                poll.poll_options.all().delete()
                PollOption.objects.bulk_create([
                    PollOption(poll=poll, text=text, order=i, vote_count=0)
                    for i, text in enumerate(clean)
                ])

        poll.refresh_from_db()
        return CommunityPollType.from_model(poll, user)

    @strawberry.mutation
    def change_vote(
        self,
        info: strawberry.types.Info,
        poll_id: strawberry.ID,
        new_option_id: strawberry.ID,
    ) -> ChangeVoteResult:
        """
        Change an existing vote to a different option.

        Anti-gaming guarantees (all enforced server-side):
          • Updates the EXISTING Vote row — never deletes and reinserts.
            UNIQUE(poll, user) is always intact; total_votes never drifts.
          • Rate-limited: at most VOTE_CHANGE_MAX changes per user per poll.
          • Cooldown: VOTE_CHANGE_COOLDOWN_SECONDS must elapse between changes.
          • Lock-in: no changes within VOTE_CHANGE_LOCK_IN_MINUTES of close.
          • Idempotent: same option = no-op (no log entry, no count increment).
          • Audit: every real change writes a VoteChange log row (append-only).
          • Anonymity: user identity in VoteChange is never returned by the API.
        """
        user = require_auth(info)
        now = timezone.now()

        try:
            poll = CommunityPoll.objects.prefetch_related('poll_options').get(
                id=str(poll_id)
            )
        except CommunityPoll.DoesNotExist:
            raise Exception("Poll not found")

        # ── Guard: poll closed ────────────────────────────────────────────────
        if poll.ends_at and poll.ends_at <= now:
            return ChangeVoteError(
                code="POLL_CLOSED",
                message="This poll has ended and no longer accepts vote changes.",
            )

        # ── Guard: vote-change disabled on this poll ──────────────────────────
        if not poll.allow_vote_change:
            if poll.verified_only:
                reason = "Verified-only polls disable vote changes to preserve integrity."
            elif poll.hide_results_until_close:
                reason = "Hidden-result polls disable vote changes until the poll closes."
            else:
                reason = "Vote changes are not allowed on this poll."
            return ChangeVoteError(code="CHANGE_DISABLED", message=reason)

        # ── Guard: lock-in window ─────────────────────────────────────────────
        if poll.ends_at:
            seconds_to_close = (poll.ends_at - now).total_seconds()
            if seconds_to_close <= VOTE_CHANGE_LOCK_IN_MINUTES * 60:
                return ChangeVoteError(
                    code="CHANGE_WINDOW_CLOSED",
                    message=(
                        f"Vote changes are locked in the final "
                        f"{VOTE_CHANGE_LOCK_IN_MINUTES} minutes before this poll closes."
                    ),
                )

        # ── Guard: option belongs to this poll ────────────────────────────────
        try:
            new_option = poll.poll_options.get(id=str(new_option_id))
        except PollOption.DoesNotExist:
            return ChangeVoteError(
                code="INVALID_OPTION",
                message="That option does not exist on this poll.",
            )

        # ── Fetch existing vote row ───────────────────────────────────────────
        try:
            vote = CommunityPollVote.objects.select_related('option').get(
                poll=poll, user=user
            )
        except CommunityPollVote.DoesNotExist:
            return ChangeVoteError(
                code="NOT_VOTED",
                message="You haven't voted on this poll yet. Use castVote first.",
            )

        # ── Idempotency: same option → no-op ─────────────────────────────────
        if vote.option_id == new_option.pk:
            poll.refresh_from_db()
            return CommunityPollType.from_model(poll, user)

        # ── Guard: change limit ───────────────────────────────────────────────
        if vote.change_count >= VOTE_CHANGE_MAX:
            return ChangeVoteError(
                code="CHANGE_LIMIT_REACHED",
                message=(
                    f"You have used all {VOTE_CHANGE_MAX} allowed vote changes on this poll."
                ),
            )

        # ── Guard: cooldown ───────────────────────────────────────────────────
        if vote.last_changed_at:
            elapsed = (now - vote.last_changed_at).total_seconds()
            if elapsed < VOTE_CHANGE_COOLDOWN_SECONDS:
                wait = int(VOTE_CHANGE_COOLDOWN_SECONDS - elapsed) + 1
                return ChangeVoteError(
                    code="CHANGE_TOO_SOON",
                    message=f"Please wait {wait} more second(s) before changing your vote.",
                )

        # ── Atomic update ─────────────────────────────────────────────────────
        old_option = vote.option
        with transaction.atomic():
            # Shift vote_count between options atomically.
            # vote_count is PositiveIntegerField; old option must have ≥1 vote.
            PollOption.objects.filter(pk=old_option.pk).update(
                vote_count=F('vote_count') - 1
            )
            PollOption.objects.filter(pk=new_option.pk).update(
                vote_count=F('vote_count') + 1
            )

            # UPDATE the existing Vote row — never delete+insert.
            # This keeps UNIQUE(poll, user) satisfied at all times and
            # total_votes unchanged (it was already counted for this user).
            CommunityPollVote.objects.filter(pk=vote.pk).update(
                option=new_option,
                change_count=F('change_count') + 1,
                last_changed_at=now,
            )

            # Append audit log entry.
            # user is stored internally; it is NEVER returned via any API field.
            VoteChange.objects.create(
                poll=poll,
                user=user,
                from_option=old_option,
                to_option=new_option,
                changed_at=now,
            )

        poll.refresh_from_db()
        return CommunityPollType.from_model(poll, user)
