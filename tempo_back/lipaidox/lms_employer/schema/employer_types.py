import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.employer import (
    EmployerProfile,
    TalentPoolSearch,
    EmployerStudentContact,
    EmployerDashboardStats
)

@strawberry.type
class EmployerDashboardStatsNode:
    id: strawberry.ID
    employerId: strawberry.ID
    
    # Job Statistics
    totalViews: int
    totalApplications: int
    pendingApplications: int
    hiredCount: int
    
    # Talent Pool Statistics
    profileViews: int
    contactsSent: int
    contactsAccepted: int
    
    # Engagement Metrics
    avgResponseTimeHours: float
    conversionRate: float
    
    # Period
    statsPeriodStart: datetime
    statsPeriodEnd: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: EmployerDashboardStats):
        return cls(
            id=strawberry.ID(str(instance.id)),
            employerId=strawberry.ID(str(instance.employer.id)),
            totalViews=instance.total_views,
            totalApplications=instance.total_applications,
            pendingApplications=instance.pending_applications,
            hiredCount=instance.hired_count,
            profileViews=instance.profile_views,
            contactsSent=instance.contacts_sent,
            contactsAccepted=instance.contacts_accepted,
            avgResponseTimeHours=instance.avg_response_time_hours,
            conversionRate=instance.conversion_rate,
            statsPeriodStart=instance.stats_period_start,
            statsPeriodEnd=instance.stats_period_end,
            updatedAt=instance.updated_at,
        )

@strawberry.type
class EmployerStudentContactNode:
    id: strawberry.ID
    employerId: strawberry.ID
    employerName: str
    studentId: strawberry.ID
    studentName: str
    message: str
    jobListingId: Optional[str]
    jobListingTitle: Optional[str]
    status: str
    studentResponse: Optional[str]
    respondedAt: Optional[datetime]
    source: str
    priority: str
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: EmployerStudentContact):
        return cls(
            id=strawberry.ID(str(instance.id)),
            employerId=strawberry.ID(str(instance.employer.id)),
            employerName=instance.employer.company_name,
            studentId=strawberry.ID(str(instance.student.id)),
            studentName=instance.student.user.username,
            message=instance.message,
            jobListingId=str(instance.job_listing.id) if instance.job_listing else None,
            jobListingTitle=instance.job_listing.title if instance.job_listing else None,
            status=instance.status,
            studentResponse=instance.student_response,
            respondedAt=instance.responded_at,
            source=instance.source,
            priority=instance.priority,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )

@strawberry.type
class TalentPoolSearchNode:
    id: strawberry.ID
    employerId: strawberry.ID
    employerName: str
    filtersJsonStr: str  # JSON string instead of dict
    searchQuery: Optional[str]
    resultsCount: int
    savedProfiles: List[str]  # Student profile IDs
    searchedAt: datetime

    @classmethod
    def from_model(cls, instance: TalentPoolSearch):
        import json
        return cls(
            id=strawberry.ID(str(instance.id)),
            employerId=strawberry.ID(str(instance.employer.id)),
            employerName=instance.employer.company_name,
            filtersJsonStr=json.dumps(instance.filters_json),
            searchQuery=instance.search_query,
            resultsCount=instance.results_count,
            savedProfiles=instance.saved_profiles,
            searchedAt=instance.searched_at,
        )

@strawberry.type
class EmployerProfileNode:
    id: strawberry.ID
    userId: strawberry.ID
    companyName: str
    industry: str
    companySize: str
    description: str
    mission: Optional[str]
    values: List[str]
    logoUrl: Optional[str]
    website: Optional[str]
    headquarters: Optional[str]
    locations: List[str]
    linkedinUrl: Optional[str]
    twitterUrl: Optional[str]
    hrContactEmail: Optional[str]
    recruitmentTeamSize: int
    isVerified: bool
    verifiedAt: Optional[datetime]
    totalJobPostings: int
    activeJobPostings: int
    totalApplications: int
    planType: str
    planExpiresAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime
    
    # Computed properties
    canPostJobs: bool
    
    # Related data
    dashboardStats: Optional[EmployerDashboardStatsNode]
    recentContacts: List[EmployerStudentContactNode]
    recentSearches: List[TalentPoolSearchNode]

    @classmethod
    def from_model(cls, instance: EmployerProfile, include_stats=False, include_contacts=False, include_searches=False):
        dashboard_stats = None
        recent_contacts = []
        recent_searches = []
        
        if include_stats:
            stats = getattr(instance, 'dashboard_stats', None)
            if stats:
                dashboard_stats = EmployerDashboardStatsNode.from_model(stats)
        
        if include_contacts:
            contacts = instance.student_contacts.order_by('-created_at')[:5]
            recent_contacts = [EmployerStudentContactNode.from_model(contact) for contact in contacts]
        
        if include_searches:
            searches = instance.talent_searches.order_by('-searched_at')[:5]
            recent_searches = [TalentPoolSearchNode.from_model(search) for search in searches]
        
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user.id)),
            companyName=instance.company_name,
            industry=instance.industry,
            companySize=instance.company_size,
            description=instance.description,
            mission=instance.mission,
            values=instance.values,
            logoUrl=instance.logo_url,
            website=instance.website,
            headquarters=instance.headquarters,
            locations=instance.locations,
            linkedinUrl=instance.linkedin_url,
            twitterUrl=instance.twitter_url,
            hrContactEmail=instance.hr_contact_email,
            recruitmentTeamSize=instance.recruitment_team_size,
            isVerified=instance.is_verified,
            verifiedAt=instance.verified_at,
            totalJobPostings=instance.total_job_postings,
            activeJobPostings=instance.active_job_postings,
            totalApplications=instance.total_applications,
            planType=instance.plan_type,
            planExpiresAt=instance.plan_expires_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
            canPostJobs=instance.can_post_jobs(),
            dashboardStats=dashboard_stats,
            recentContacts=recent_contacts,
            recentSearches=recent_searches,
        )
