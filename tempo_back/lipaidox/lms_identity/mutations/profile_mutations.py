import strawberry
from typing import List, Optional
from datetime import date
from ..schema.types import (
    StudentNode, InstructorNode, WorkExperienceNode, 
    EducationRecordNode, ExternalCertificationNode, StudentProjectNode
)
from ..models import (
    StudentProfile, InstructorProfile, WorkExperience, 
    EducationRecord, ExternalCertification, Project
)

@strawberry.type
class ProfileMutations:
    # --- Student Profile ---
    @strawberry.mutation
    def update_student_profile(
        self,
        info,
        headline: Optional[str] = None,
        bio: Optional[str] = None,
        location: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        linkedin: Optional[str] = None,
        github: Optional[str] = None,
        portfolio: Optional[str] = None,
        employment_status: Optional[str] = None,
        years_of_experience: Optional[int] = None,
        career_goals: Optional[List[str]] = None,
        desired_roles: Optional[List[str]] = None,
        onboarding_step: Optional[int] = None,
        remote_preference: Optional[bool] = None,
        willing_to_relocate: Optional[bool] = None,
    ) -> StudentNode:
        user = info.context.request.user
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        
        if headline is not None: profile.headline = headline
        if bio is not None: profile.bio = bio
        if location is not None: profile.location = location
        if phone is not None: profile.phone = phone
        if website is not None: profile.website = website
        if linkedin is not None: profile.linkedin = linkedin
        if github is not None: profile.github = github
        if portfolio is not None: profile.portfolio = portfolio
        if employment_status is not None: profile.employment_status = employment_status
        if years_of_experience is not None: profile.years_of_experience = years_of_experience
        if career_goals is not None: profile.career_goals = career_goals
        if desired_roles is not None: profile.desired_roles = desired_roles
        if onboarding_step is not None: profile.onboarding_step = onboarding_step
        if remote_preference is not None: profile.remote_preference = remote_preference
        if willing_to_relocate is not None: profile.willing_to_relocate = willing_to_relocate
        
        profile.save()
        return StudentNode.from_model(profile)

    # --- Instructor Profile ---
    @strawberry.mutation
    def register_as_instructor(
        self,
        info,
        headline: str,
        bio: str,
        specializations: List[str]
    ) -> InstructorNode:
        user = info.context.request.user
        instructor, created = InstructorProfile.objects.get_or_create(
            user=user,
            defaults={
                'headline': headline,
                'bio': bio,
                'specializations': specializations,
                'tenant': getattr(user, 'tenant', None)
            }
        )
        return InstructorNode.from_model(instructor)

    @strawberry.mutation
    def update_instructor_profile(
        self,
        info,
        headline: Optional[str] = None,
        bio: Optional[str] = None,
        specializations: Optional[List[str]] = None
    ) -> InstructorNode:
        user = info.context.request.user
        profile = InstructorProfile.objects.get(user=user)
        
        if headline is not None: profile.headline = headline
        if bio is not None: profile.bio = bio
        if specializations is not None: profile.specializations = specializations
        
        profile.save()
        return InstructorNode.from_model(profile)
