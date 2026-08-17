import strawberry
import logging
from lipaidox.auth.queries import AuthQuery
from lipaidox.auth.mutations import AuthMutation
from lipaidox.queries import TenantQuery
from lipaidox.mutations import TenantMutation
from lipaidox.onboarding.queries.onboarding_query import OnboardingQuery
from lipaidox.onboarding.mutations.onboarding_mutation import OnboardingMutation
from lipaidox.creator_profile.queries.profile_query import ProfileQuery
from lipaidox.creator_profile.mutations.profile_mutation import ProfileMutation
from lipaidox.creator_profile.queries.username_query import UsernameQuery
from lipaidox.creator_profile.queries.membership_query import MembershipQuery
from lipaidox.creator_profile.mutations.membership_mutation import MembershipMutation
from lipaidox.creator_profile.queries.review_query import ReviewQuery
from lipaidox.creator_profile.mutations.review_mutation import ReviewMutation
from lipaidox.content_classification.queries.cc_query import ContentClassificationQuery
from lipaidox.content_classification.mutations.cc_mutation import ContentClassificationMutation
from lipaidox.kyc.queries.kyc_query import KYCQuery
from lipaidox.kyc.mutations.kyc_mutation import KYCMutation
from lipaidox.payment.queries.payment_query import PaymentQuery
from lipaidox.payment.mutations.payment_mutation import PaymentMutation
from lipaidox.payment.queries.gateway_query import GatewayQuery
from lipaidox.payment.mutations.gateway_mutation import GatewayMutation
from lipaidox.monetization.queries.monetization_query import MonetizationQuery
from lipaidox.monetization.mutations.monetization_mutation import MonetizationMutation
from lipaidox.content.queries.content_query import ContentQuery
from lipaidox.content.queries.content_insights_query import ContentInsightsQuery
from lipaidox.content.mutations.content_mutation import ContentMutation
from lipaidox.content.queries.content_report_query import ContentReportQuery
from lipaidox.content.mutations.content_report_mutation import ContentReportMutation
from lipaidox.content.queries.content_review_query import ContentReviewQuery
from lipaidox.content.mutations.content_review_mutation import ContentReviewMutation
from lipaidox.content.queries.content_comment_query import ContentCommentQuery
from lipaidox.content.mutations.content_comment_mutation import ContentCommentMutation
from lipaidox.content.mutations.content_interaction_mutation import (
    ContentInteractionMutation,
    ContentInteractionQuery,
)
from lipaidox.subscriptions.queries.subscription_query import SubscriptionQuery
from lipaidox.subscriptions.mutations.subscription_mutation import SubscriptionMutation
from lipaidox.creator_plans.queries.plan_query import CreatorPlanQuery
from lipaidox.creator_plans.mutations.plan_mutation import CreatorPlanMutation
from lipaidox.admin_panel.queries.admin_query import AdminPanelQuery
from lipaidox.admin_panel.mutations.admin_mutation import AdminPanelMutation
from lipaidox.admin_panel.mutations.announcement_mutation import AnnouncementMutation, PlatformPostMutation
from lipaidox.credits.queries.credits_query import CreditsQuery
from lipaidox.credits.mutations.credits_mutation import CreditsMutation
from lipaidox.ppv.queries.ppv_query import PPVQuery
from lipaidox.ppv.mutations.ppv_mutation import PPVMutation
from lipaidox.tips.queries.tips_query import TipsQuery
from lipaidox.tips.mutations.tips_mutation import TipsMutation
from lipaidox.wallet.queries.wallet_query import WalletQuery
from lipaidox.wallet.mutations.wallet_mutation import WalletMutation
from lipaidox.ai_intelligence.queries.ai_intelligence_query import AIIntelligenceQuery
from lipaidox.ai_intelligence.mutations.ai_intelligence_mutation import AIIntelligenceMutation
from lipaidox.recommendation.queries.recommendation_query import RecommendationQuery
from lipaidox.recommendation.mutations.recommendation_mutation import RecommendationMutation
from lipaidox.live_streaming.queries.live_streaming_query import LiveStreamingQuery
from lipaidox.live_streaming.mutations.live_streaming_mutation import LiveStreamingMutation
from lipaidox.lost_found.queries.community_query import CommunityQuery as LostFoundCommunityQuery
from lipaidox.lost_found.mutations.community_mutation import CommunityMutation as LostFoundCommunityMutation
from lipaidox.lms_identity.queries import StudentQueries
from lipaidox.lms_identity.mutations import ProfileMutations
from lipaidox.lms_content.queries import ContentQueries
from lipaidox.lms_content.mutations import ContentMutations
from lipaidox.lms_learning.queries import LearningQueries
from lipaidox.lms_learning.mutations import LearningMutations
from lipaidox.lms_community.queries import CommunityQueries
from lipaidox.lms_community.mutations import CommunityMutations
from lipaidox.lms_certification.queries import CertificationQueries
from lipaidox.lms_certification.mutations import CertificationMutations
from lipaidox.lms_skills.queries import SkillsQueries
from lipaidox.lms_skills.mutations import SkillsMutations
from lipaidox.lms_performance.queries import PerformanceQueries
from lipaidox.lms_performance.mutations import PerformanceMutations
from lipaidox.lms_financial.queries import FinancialQueries
from lipaidox.lms_financial.mutations import FinancialMutations
from lipaidox.lms_careers.queries import CareerQueries
from lipaidox.lms_careers.mutations import CareerMutations
from lipaidox.lms_messages.queries import LmsMessageQueries
from lipaidox.lms_messages.mutations import LmsMessageMutations
from lipaidox.lms_notifications.queries import LmsNotificationQueries
from lipaidox.lms_notifications.mutations import LmsNotificationMutations
from lipaidox.lms_cohorts.queries import LmsCohortQueries
from lipaidox.lms_cohorts.mutations import LmsCohortMutations
from lipaidox.lms_employer.queries import LmsEmployerQueries
from lipaidox.lms_employer.mutations import LmsEmployerMutations
from lipaidox.lms_onboarding.queries import LmsOnboardingQueries
from lipaidox.lms_onboarding.mutations import LmsOnboardingMutations
from lipaidox.messaging.queries import MessagingQueries
from lipaidox.messaging.mutations import MessagingMutations
from lipaidox.notifications.queries import NotificationQuery
from lipaidox.notifications.mutations import NotificationMutation

logger = logging.getLogger(__name__)

@strawberry.type
class Query(
    AuthQuery, 
    TenantQuery, 
    OnboardingQuery, 
    ProfileQuery,
    UsernameQuery,
    MembershipQuery,
    ReviewQuery,
    # Creator-platform notifications. Must stay AHEAD of LmsNotificationQueries:
    # both classes define `my_notifications`, and MRO gives the field to the first
    # base listed. The creator resolver is the one the apps query (it returns the
    # richer NotificationType with recipientId/priority/entityType).
    NotificationQuery,
    StudentQueries,
    ContentQueries,
    LearningQueries,
    CommunityQueries,
    CertificationQueries,
    SkillsQueries,
    PerformanceQueries,
    FinancialQueries,
    CareerQueries,
    LmsMessageQueries,
    LmsNotificationQueries,
    LmsCohortQueries,
    LmsEmployerQueries,
    LmsOnboardingQueries,
    ContentClassificationQuery, 
    KYCQuery,
    PaymentQuery,
    GatewayQuery,
    MonetizationQuery,
    ContentQuery,
    ContentInsightsQuery,
    ContentReportQuery,
    ContentReviewQuery,
    ContentCommentQuery,
    ContentInteractionQuery,
    SubscriptionQuery,
    CreatorPlanQuery,
    AdminPanelQuery,
    CreditsQuery,
    PPVQuery,
    TipsQuery,
    WalletQuery,
    AIIntelligenceQuery,
    RecommendationQuery,
    LiveStreamingQuery,
    LostFoundCommunityQuery,
    MessagingQueries,
):
    @strawberry.field
    def hello(self) -> str:
        return "Hello! Your Strawberry GraphQL endpoint is working."

@strawberry.type
class Mutation(
    AuthMutation, 
    TenantMutation, 
    OnboardingMutation, 
    ProfileMutation,
    MembershipMutation,
    ReviewMutation,
    # See the note on NotificationQuery above — same collision on
    # mark_notification_read / mark_all_notifications_read / create_notification /
    # delete_notification, resolved the same way.
    NotificationMutation,
    ProfileMutations,
    ContentMutations,
    LearningMutations,
    CommunityMutations,
    CertificationMutations,
    SkillsMutations,
    PerformanceMutations,
    FinancialMutations,
    CareerMutations,
    LmsMessageMutations,
    LmsNotificationMutations,
    LmsCohortMutations,
    LmsEmployerMutations,
    LmsOnboardingMutations,
    ContentClassificationMutation, 
    KYCMutation,
    PaymentMutation,
    GatewayMutation,
    MonetizationMutation,
    ContentMutation,
    ContentReportMutation,
    ContentReviewMutation,
    ContentCommentMutation,
    ContentInteractionMutation,
    SubscriptionMutation,
    CreatorPlanMutation,
    AdminPanelMutation,
    AnnouncementMutation,
    PlatformPostMutation,
    CreditsMutation,
    PPVMutation,
    TipsMutation,
    WalletMutation,
    AIIntelligenceMutation,
    RecommendationMutation,
    LiveStreamingMutation,
    LostFoundCommunityMutation,
    MessagingMutations,
):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)
