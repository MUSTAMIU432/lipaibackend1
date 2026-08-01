import strawberry
from typing import Optional, List
from datetime import date
from ..schema.types import (
    WorkExperienceNode, EducationRecordNode, 
    ExternalCertificationNode, StudentProjectNode
)
from ..models import (
    StudentProfile, WorkExperience, EducationRecord, 
    ExternalCertification, Project
)

@strawberry.type
class ProfessionalMutations:
    # --- Work Experience ---
    @strawberry.mutation
    def add_work_experience(
        self,
        info,
        company: str,
        position: str,
        start_date: date,
        location: Optional[str] = None,
        location_type: str = "onsite",
        is_current: bool = False,
        end_date: Optional[date] = None,
        description: Optional[str] = None,
        achievements: Optional[List[str]] = None,
        skills: Optional[List[str]] = None
    ) -> WorkExperienceNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        exp = WorkExperience.objects.create(
            student=student,
            company=company,
            position=position,
            start_date=start_date,
            location=location,
            location_type=location_type,
            is_current=is_current,
            end_date=end_date,
            description=description,
            achievements=achievements or [],
            skills=skills or []
        )
        return WorkExperienceNode.from_model(exp)

    @strawberry.mutation
    def update_work_experience(
        self,
        info,
        experience_id: strawberry.ID,
        company: Optional[str] = None,
        position: Optional[str] = None,
        # ... and other fields ...
    ) -> WorkExperienceNode:
        exp = WorkExperience.objects.get(id=experience_id)
        if company: exp.company = company
        if position: exp.position = position
        # Simplified update logic for the example
        exp.save()
        return WorkExperienceNode.from_model(exp)

    @strawberry.mutation
    def delete_work_experience(self, info, experience_id: strawberry.ID) -> bool:
        WorkExperience.objects.filter(id=experience_id).delete()
        return True

    # --- Education ---
    @strawberry.mutation
    def add_education_record(
        self,
        info,
        institution: str,
        degree: str,
        field_of_study: str,
        start_date: date,
        location: Optional[str] = None,
        is_current: bool = False,
        end_date: Optional[date] = None,
        description: Optional[str] = None
    ) -> EducationRecordNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        edu = EducationRecord.objects.create(
            student=student,
            institution=institution,
            degree=degree,
            field_of_study=field_of_study,
            start_date=start_date,
            location=location,
            is_current=is_current,
            end_date=end_date,
            description=description
        )
        return EducationRecordNode.from_model(edu)

    # --- Project ---
    @strawberry.mutation
    def add_student_project(
        self,
        info,
        title: str,
        description: str,
        url: Optional[str] = None,
        github_url: Optional[str] = None,
        technologies: Optional[List[str]] = None,
        is_featured: bool = False
    ) -> StudentProjectNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        p = Project.objects.create(
            student=student,
            title=title,
            description=description,
            url=url,
            github_url=github_url,
            technologies=technologies or [],
            is_featured=is_featured
        )
        return StudentProjectNode.from_model(p)

    # --- External Certification ---
    @strawberry.mutation
    def add_external_certification(
        self,
        info,
        name: str,
        issuer: str,
        issue_date: date,
        expiry_date: Optional[date] = None,
        credential_id: Optional[str] = None,
        credential_url: Optional[str] = None,
        skills: Optional[List[str]] = None
    ) -> ExternalCertificationNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        cert = ExternalCertification.objects.create(
            student=student,
            name=name,
            issuer=issuer,
            issue_date=issue_date,
            expiry_date=expiry_date,
            credential_id=credential_id,
            credential_url=credential_url,
            skills=skills or []
        )
        return ExternalCertificationNode.from_model(cert)
