import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.job import JobListing

@strawberry.type
class JobListingNode:
    id: strawberry.ID
    title: str
    company: str
    location: str
    jobType: str
    salaryMin: Optional[float]
    salaryMax: Optional[float]
    currency: str
    description: str
    requiredSkills: List[str]
    status: str
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: JobListing):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            company=instance.company,
            location=instance.location,
            jobType=instance.job_type,
            salaryMin=float(instance.salary_min) if instance.salary_min else None,
            salaryMax=float(instance.salary_max) if instance.salary_max else None,
            currency=instance.currency,
            description=instance.description,
            requiredSkills=instance.required_skills or [],
            status=instance.status,
            createdAt=instance.created_at,
        )
