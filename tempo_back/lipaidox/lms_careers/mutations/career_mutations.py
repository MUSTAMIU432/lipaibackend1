import strawberry
from typing import Optional, List
from ..schema.application_types import JobApplicationNode
from ..schema.talent_types import TalentPoolProfileNode
from ..models.job import JobListing
from ..models.application import JobApplication
from ..models.talent import TalentPoolProfile
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class CareerMutations:
    @strawberry.mutation
    def apply_for_job(
        self,
        info,
        job_id: strawberry.ID,
        resume_url: str,
        cover_letter: Optional[str] = None
    ) -> JobApplicationNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
            
        student = StudentProfile.objects.get(user=user)
        job = JobListing.objects.get(id=job_id)
        
        application, created = JobApplication.objects.get_or_create(
            student=student,
            job=job,
            defaults={'resume_url': resume_url, 'cover_letter': cover_letter}
        )
        return JobApplicationNode.from_model(application)

    @strawberry.mutation
    def update_talent_pool_profile(
        self,
        info,
        is_visible: bool,
        bio: Optional[str] = None,
        skills: Optional[List[str]] = None,
        desired_salary: Optional[float] = None,
        availability: Optional[str] = None
    ) -> TalentPoolProfileNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        profile, created = TalentPoolProfile.objects.get_or_create(
            student=student,
            defaults={'tenant': user.tenant}
        )
        
        profile.is_visible = is_visible
        if bio is not None: profile.bio = bio
        if skills is not None: profile.skills = skills
        if desired_salary is not None: profile.desired_salary = desired_salary
        if availability is not None: profile.availability = availability
        
        profile.save()
        return TalentPoolProfileNode.from_model(profile)

    @strawberry.mutation
    def post_job_listing(
        self,
        info,
        title: str,
        company: str,
        location: str,
        description: str,
        job_type: str = "remote",
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        required_skills: List[str] = None
    ) -> bool:
        user = info.context.request.user
        # Simplified: check for instructor or employer role here
        JobListing.objects.create(
            employer=user,
            title=title,
            company=company,
            location=location,
            description=description,
            job_type=job_type,
            salary_min=salary_min,
            salary_max=salary_max,
            required_skills=required_skills or [],
            tenant=user.tenant
        )
        return True
