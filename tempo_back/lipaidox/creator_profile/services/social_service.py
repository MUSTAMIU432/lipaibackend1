"""Shared helpers for Follow / Membership / Review resolvers.

Counts are always derived from the real relationship tables; nothing trusts a
client-supplied count.
"""
from django.db.models import Avg, Count, Q

from ..models import CreatorProfile, MembershipSubscription, MembershipStatus, Review, ReviewStatus


def require_user(info):
    user = info.context.request.user
    if not getattr(user, "is_authenticated", False):
        raise Exception("Authentication required")
    return user


def get_target_profile(target_user_id):
    """Resolve a target creator by their *User* id (consistent with the follow API)."""
    try:
        return CreatorProfile.objects.get(user_id=target_user_id)
    except CreatorProfile.DoesNotExist:
        raise Exception("Creator not found")


def creator_summary_fields(profile: CreatorProfile):
    user = profile.user
    return dict(
        userId=str(profile.user_id),
        username=profile.username or user.username,
        displayName=profile.username or user.username,
        avatar=profile.profile_photo_url,
        isVerified=profile.is_verified,
    )


def subscriber_user_fields(user):
    profile = getattr(user, "profile", None)
    return dict(
        id=str(user.id),
        username=user.username,
        displayName=(profile.username if profile else user.username),
        avatar=(profile.profile_photo_url if profile else None),
        isVerified=(profile.is_verified if profile else False),
        isCreator=(user.role == "creator"),
    )


# ── Subscriber count (source of truth = active MembershipSubscription rows) ─────

def active_subscriber_count(profile: CreatorProfile) -> int:
    return MembershipSubscription.objects.filter(
        target=profile, status=MembershipStatus.ACTIVE
    ).count()


def recalc_subscriber_count(profile: CreatorProfile) -> int:
    count = active_subscriber_count(profile)
    if profile.subscriber_count != count:
        profile.subscriber_count = count
        profile.save(update_fields=["subscriber_count"])
    return count


# ── Review aggregates (source of truth = published, non-deleted reviews) ────────

def published_reviews(profile: CreatorProfile):
    return Review.objects.filter(
        target=profile, status=ReviewStatus.PUBLISHED, deleted_at__isnull=True
    )


def review_summary(profile: CreatorProfile) -> dict:
    qs = published_reviews(profile)
    agg = qs.aggregate(
        avg=Avg("rating"),
        total=Count("id"),
        verified=Count("id", filter=Q(is_verified=True)),
        one=Count("id", filter=Q(rating=1)),
        two=Count("id", filter=Q(rating=2)),
        three=Count("id", filter=Q(rating=3)),
        four=Count("id", filter=Q(rating=4)),
        five=Count("id", filter=Q(rating=5)),
    )
    return {
        "averageRating": round(float(agg["avg"] or 0.0), 2),
        "totalReviews": agg["total"] or 0,
        "verifiedReviews": agg["verified"] or 0,
        "oneStar": agg["one"] or 0,
        "twoStar": agg["two"] or 0,
        "threeStar": agg["three"] or 0,
        "fourStar": agg["four"] or 0,
        "fiveStar": agg["five"] or 0,
    }


# ── Recalculation utilities (idempotent; safe to run as a backfill) ─────────────

def recalc_all_subscriber_counts() -> int:
    updated = 0
    for profile in CreatorProfile.objects.all().iterator():
        before = profile.subscriber_count
        if recalc_subscriber_count(profile) != before:
            updated += 1
    return updated
