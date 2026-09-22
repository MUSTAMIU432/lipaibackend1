"""
Creator monetization eligibility — every requirement below reads a real
column the platform already tracks (age, plan tier, followers, published
content, account status, payout method, tax withholding, verification).

Two of the mockup's ten line items — "Tax Registration" and "Tax/Payment
Information" — collapse into one (`tax_payment_info`) here: the only tax
signal this backend actually has is `PaymentMethod.tax_withholding_rate`,
and a business's formal registration number lives behind the separate KYC
`BusinessVerification` flow, not this quick check. Inventing a second,
always-green tax item to hit the mockup's count would be exactly the kind
of "looks live and quietly does nothing" row this codebase's own
`settings/index.tsx` comment warns against — so it's nine honest checks,
not ten decorative ones. Likewise "Qualified Impressions" is approximated
from lifetime published-content views (`Content.view_count`), since there
is no rolling impressions-by-day log to compute a true 30/60/90-day window.
"""
import strawberry
from datetime import date
from typing import List, Optional


@strawberry.type
class CreatorEligibilityRequirementType:
    key: str
    label: str
    description: str
    met: bool
    # What the row shows in place of a checkmark when it isn't met — usually
    # "why not", sometimes just a value ("342 / 1,000 followers").
    detail: Optional[str] = None


@strawberry.type
class CreatorEligibilityType:
    metCount: int
    totalCount: int
    percent: int
    eligible: bool
    requirements: List[CreatorEligibilityRequirementType]


MIN_FOLLOWERS = 1000
MIN_QUALIFIED_VIEWS = 100_000
MIN_AGE_YEARS = 18
# The mockup's own ring reads "Eligible" at 8/10 (80%), not 10/10 — some
# requirements (payout method, tax info) are things a creator finishes
# after they're otherwise ready, not gates on seeing the programs at all.
ELIGIBLE_THRESHOLD_PERCENT = 80


def _age_years(born: Optional[date]) -> Optional[int]:
    if born is None:
        return None
    today = date.today()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def compute_creator_eligibility(user) -> CreatorEligibilityType:
    from lipaidox.creator_profile.models import CreatorProfile, ProfileStatus
    from lipaidox.creator_plans.constants import CreatorPlanTier
    from lipaidox.content.models.content import Content, ContentStatus
    from lipaidox.payment.models.method import PaymentMethod, PaymentMethodStatus, TaxWithholdingRate

    profile = CreatorProfile.objects.filter(user=user).first()

    rows: List[CreatorEligibilityRequirementType] = []

    # 1. Age
    age = _age_years(getattr(user, "date_of_birth", None))
    age_met = age is not None and age >= MIN_AGE_YEARS
    rows.append(CreatorEligibilityRequirementType(
        key="age",
        label="Age Requirement",
        description=f"At least {MIN_AGE_YEARS} years old",
        met=age_met,
        detail=None if age_met else ("Add your date of birth" if age is None else "Under the minimum age"),
    ))

    # 2. Premium plan
    plan_tier = getattr(profile, "plan_tier", None) or CreatorPlanTier.FREE
    plan_met = plan_tier in (CreatorPlanTier.GO_PLUS, CreatorPlanTier.PREMIUM)
    rows.append(CreatorEligibilityRequirementType(
        key="plan",
        label="Premium Plan",
        description="Have an active Lipaidox Premium plan (Go Plus or Premium)",
        met=plan_met,
        detail=None if plan_met else f"Current plan: {(plan_tier or 'free').replace('_', ' ').title()}",
    ))

    # 3. Followers
    followers = getattr(profile, "follower_count", 0) or 0
    followers_met = followers >= MIN_FOLLOWERS
    rows.append(CreatorEligibilityRequirementType(
        key="followers",
        label="Followers",
        description=f"At least {MIN_FOLLOWERS:,} followers",
        met=followers_met,
        detail=None if followers_met else f"{followers:,} / {MIN_FOLLOWERS:,} followers",
    ))

    # 4. Qualified views (lifetime, published content — the closest real proxy
    # to "impressions" this backend tracks).
    qualified_views = 0
    if profile is not None:
        from django.db.models import Sum
        qualified_views = (
            Content.objects.filter(creator=profile, status=ContentStatus.PUBLISHED)
            .aggregate(total=Sum("view_count"))
            .get("total") or 0
        )
    views_met = qualified_views >= MIN_QUALIFIED_VIEWS
    rows.append(CreatorEligibilityRequirementType(
        key="qualified_views",
        label="Qualified Views",
        description=f"Reach {MIN_QUALIFIED_VIEWS:,} views across your published content",
        met=views_met,
        detail=None if views_met else f"{qualified_views:,} / {MIN_QUALIFIED_VIEWS:,} views",
    ))

    # 5. Original content
    published_count = (
        Content.objects.filter(creator=profile, status=ContentStatus.PUBLISHED).count()
        if profile is not None else 0
    )
    content_met = published_count >= 1
    rows.append(CreatorEligibilityRequirementType(
        key="original_content",
        label="Original Content",
        description="Post original content consistently",
        met=content_met,
        detail=None if content_met else "Publish your first post",
    ))

    # 6. Account standing
    standing_met = profile is not None and profile.status not in (
        ProfileStatus.SUSPENDED, ProfileStatus.DEACTIVATED,
    )
    rows.append(CreatorEligibilityRequirementType(
        key="account_standing",
        label="Account Standing",
        description="Maintain an account in good standing",
        met=standing_met,
        detail=None if standing_met else "Your account has a standing issue — see Help center",
    ))

    # 7 & 8. Payout method + tax/payment info — both read the primary PaymentMethod.
    primary_method = (
        PaymentMethod.objects.filter(creator=profile, is_primary=True).first()
        if profile is not None else None
    )
    payout_met = primary_method is not None and primary_method.status == PaymentMethodStatus.VERIFIED
    rows.append(CreatorEligibilityRequirementType(
        key="payout_method",
        label="Payout Method",
        description="Set up an approved payout method",
        met=payout_met,
        detail=None if payout_met else "Add a payout method in your wallet",
    ))

    tax_met = primary_method is not None and primary_method.tax_withholding_rate != TaxWithholdingRate.NONE
    rows.append(CreatorEligibilityRequirementType(
        key="tax_payment_info",
        label="Tax & Payment Information",
        description="Complete required tax and payout information",
        met=tax_met,
        detail=None if tax_met else "Finish your tax details on the payout method",
    ))

    # 9. Authority — the platform's own verification badge.
    authority_met = bool(profile is not None and profile.is_verified)
    rows.append(CreatorEligibilityRequirementType(
        key="authority",
        label="Authority",
        description="Be a verified or localized authority",
        met=authority_met,
        detail=None if authority_met else "Apply for verification from your profile",
    ))

    met_count = sum(1 for r in rows if r.met)
    total = len(rows)
    percent = round((met_count / total) * 100) if total else 0

    return CreatorEligibilityType(
        metCount=met_count,
        totalCount=total,
        percent=percent,
        eligible=percent >= ELIGIBLE_THRESHOLD_PERCENT,
        requirements=rows,
    )


def compute_subscription_eligibility(user) -> CreatorEligibilityType:
    """The Subscriptions setup wizard's own, smaller eligibility check —
    three of the nine general requirements, the ones that actually gate
    opening a subscription program: verified, in good standing, and past
    the minimum follower count. All three must pass (not the 80% threshold
    the general check uses), matching the wizard's own all-green checklist.

    "Complies with community guidelines" — the mockup's fourth line item —
    isn't included: there's no strikes/violations record on the account to
    read, and reusing "Account Standing" under two different labels would
    just be the same real check wearing a second name, not a fourth one.
    """
    from lipaidox.creator_profile.models import CreatorProfile, ProfileStatus

    profile = CreatorProfile.objects.filter(user=user).first()

    followers = getattr(profile, "follower_count", 0) or 0
    followers_met = followers >= MIN_FOLLOWERS
    standing_met = profile is not None and profile.status not in (
        ProfileStatus.SUSPENDED, ProfileStatus.DEACTIVATED,
    )
    verified_met = bool(profile is not None and profile.is_verified)

    rows = [
        CreatorEligibilityRequirementType(
            key="authority",
            label="Account is verified",
            description="Your account carries Lipaidox's verification badge",
            met=verified_met,
            detail=None if verified_met else "Apply for verification from your profile",
        ),
        CreatorEligibilityRequirementType(
            key="account_standing",
            label="Active and in good standing",
            description="No suspensions or deactivation on your account",
            met=standing_met,
            detail=None if standing_met else "Your account has a standing issue — see Help center",
        ),
        CreatorEligibilityRequirementType(
            key="followers",
            label="Minimum followers reached",
            description=f"At least {MIN_FOLLOWERS:,} followers",
            met=followers_met,
            detail=None if followers_met else f"{followers:,} / {MIN_FOLLOWERS:,} followers",
        ),
    ]

    met_count = sum(1 for r in rows if r.met)
    total = len(rows)
    percent = round((met_count / total) * 100) if total else 0

    return CreatorEligibilityType(
        metCount=met_count,
        totalCount=total,
        percent=percent,
        eligible=met_count == total,
        requirements=rows,
    )
