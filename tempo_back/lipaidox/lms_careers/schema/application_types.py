import strawberry
from datetime import datetime
from typing import Optional
from ..models.application import JobApplication
from .job_types import JobListingNode

@strawberry.type
class JobApplicationNode:
    id: strawberry.ID
    job: JobListingNode
    status: str
    resumeUrl: str
    coverLetter: Optional[str]
    appliedAt: datetime

    @classmethod
    def from_model(cls, instance: JobApplication):
        return cls(
            id=strawberry.ID(str(instance.id)),
            job=JobListingNode.from_model(instance.job),
            status=instance.status,
            resumeUrl=instance.resume_url,
            coverLetter=instance.cover_letter,
            appliedAt=instance.applied_at,
        )
