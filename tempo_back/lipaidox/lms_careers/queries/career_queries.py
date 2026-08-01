import strawberry
from typing import List, Optional
from ..schema.job_types import JobListingNode
from ..schema.application_types import JobApplicationNode
from ..schema.talent_types import TalentPoolProfileNode
from ..models.job import JobListing
from ..models.application import JobApplication
from ..models.talent import TalentPoolProfile

@strawberry.type
class CareerQueries:
    @strawberry.field
    def all_job_listings(self) -> List[JobListingNode]:
        return [JobListingNode.from_model(j) for j in JobListing.objects.filter(status='open')]

    @strawberry.field
    def my_applications(self, info) -> List[JobApplicationNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [JobApplicationNode.from_model(a) for a in JobApplication.objects.filter(student__user=user)]

    @strawberry.field
    def talent_pool_status(self, info) -> Optional[TalentPoolProfileNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        profile = TalentPoolProfile.objects.filter(student__user=user).first()
        return TalentPoolProfileNode.from_model(profile) if profile else None

    @strawberry.field
    def job_detail(self, job_id: strawberry.ID) -> Optional[JobListingNode]:
        job = JobListing.objects.filter(id=job_id).first()
        return JobListingNode.from_model(job) if job else None
