import strawberry
from typing import Optional
from ..schema.employer_types import (
    EmployerProfileNode,
    EmployerStudentContactNode,
    TalentPoolSearchNode,
    EmployerDashboardStatsNode
)
from ..models.employer import (
    EmployerProfile,
    TalentPoolSearch,
    EmployerStudentContact,
    ContactStatus,
    EmployerDashboardStats
)

@strawberry.type
class EmployerMutations:
    @strawberry.mutation
    def create_employer_profile(
        self,
        info,
        company_name: str,
        industry: str,
        company_size: str,
        description: str,
        mission: Optional[str] = None,
        values: Optional[list[str]] = None,
        website: Optional[str] = None,
        headquarters: Optional[str] = None,
        locations: Optional[list[str]] = None,
        linkedin_url: Optional[str] = None,
        twitter_url: Optional[str] = None,
        hr_contact_email: Optional[str] = None
    ) -> EmployerProfileNode:
        """Create employer profile"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if profile already exists
        if hasattr(user, 'employer_profile'):
            raise Exception("Employer profile already exists")
        
        profile = EmployerProfile.objects.create(
            user=user,
            company_name=company_name,
            industry=industry,
            company_size=company_size,
            description=description,
            mission=mission,
            values=values or [],
            website=website,
            headquarters=headquarters,
            locations=locations or [],
            linkedin_url=linkedin_url,
            twitter_url=twitter_url,
            hr_contact_email=hr_contact_email,
            tenant=user.tenant
        )
        
        return EmployerProfileNode.from_model(profile)
    
    @strawberry.mutation
    def update_employer_profile(
        self,
        info,
        company_name: Optional[str] = None,
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        description: Optional[str] = None,
        mission: Optional[str] = None,
        values: Optional[list[str]] = None,
        website: Optional[str] = None,
        headquarters: Optional[str] = None,
        locations: Optional[list[str]] = None,
        linkedin_url: Optional[str] = None,
        twitter_url: Optional[str] = None,
        hr_contact_email: Optional[str] = None
    ) -> EmployerProfileNode:
        """Update employer profile"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            profile = user.employer_profile
        except EmployerProfile.DoesNotExist:
            raise Exception("Employer profile not found")
        
        # Update fields if provided
        if company_name is not None:
            profile.company_name = company_name
        if industry is not None:
            profile.industry = industry
        if company_size is not None:
            profile.company_size = company_size
        if description is not None:
            profile.description = description
        if mission is not None:
            profile.mission = mission
        if values is not None:
            profile.values = values
        if website is not None:
            profile.website = website
        if headquarters is not None:
            profile.headquarters = headquarters
        if locations is not None:
            profile.locations = locations
        if linkedin_url is not None:
            profile.linkedin_url = linkedin_url
        if twitter_url is not None:
            profile.twitter_url = twitter_url
        if hr_contact_email is not None:
            profile.hr_contact_email = hr_contact_email
        
        profile.save()
        return EmployerProfileNode.from_model(profile)
    
    @strawberry.mutation
    def contact_student(
        self,
        info,
        student_id: strawberry.ID,
        message: str,
        job_listing_id: Optional[strawberry.ID] = None,
        priority: str = "normal"
    ) -> EmployerStudentContactNode:
        """Contact a student"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            employer = user.employer_profile
            from lipaidox.lms_identity.models import StudentProfile
            student = StudentProfile.objects.get(id=student_id)
        except (EmployerProfile.DoesNotExist, StudentProfile.DoesNotExist):
            raise Exception("Profile not found")
        
        # Check if contact already exists
        existing_contact = EmployerStudentContact.objects.filter(
            employer=employer,
            student=student
        ).first()
        
        if existing_contact:
            # Update existing contact
            existing_contact.message = message
            existing_contact.priority = priority
            if job_listing_id:
                from lipaidox.lms_careers.models import JobListing
                existing_contact.job_listing = JobListing.objects.get(id=job_listing_id)
            existing_contact.save()
            contact = existing_contact
        else:
            # Create new contact
            contact = EmployerStudentContact.objects.create(
                employer=employer,
                student=student,
                message=message,
                priority=priority,
                tenant=user.tenant
            )
            
            if job_listing_id:
                from lipaidox.lms_careers.models import JobListing
                contact.job_listing = JobListing.objects.get(id=job_listing_id)
                contact.save()
        
        return EmployerStudentContactNode.from_model(contact)
    
    @strawberry.mutation
    def respond_to_employer_contact(
        self,
        info,
        contact_id: strawberry.ID,
        response_text: str
    ) -> EmployerStudentContactNode:
        """Student responds to employer contact"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            contact = EmployerStudentContact.objects.get(
                id=contact_id,
                student=student
            )
        except (StudentProfile.DoesNotExist, EmployerStudentContact.DoesNotExist):
            raise Exception("Contact not found")
        
        contact.respond(response_text)
        return EmployerStudentContactNode.from_model(contact)
    
    @strawberry.mutation
    def accept_student_response(
        self,
        info,
        contact_id: strawberry.ID
    ) -> EmployerStudentContactNode:
        """Employer accepts student response"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            employer = user.employer_profile
            contact = EmployerStudentContact.objects.get(
                id=contact_id,
                employer=employer
            )
        except (EmployerProfile.DoesNotExist, EmployerStudentContact.DoesNotExist):
            raise Exception("Contact not found")
        
        contact.accept()
        return EmployerStudentContactNode.from_model(contact)
    
    @strawberry.mutation
    def reject_student_response(
        self,
        info,
        contact_id: strawberry.ID
    ) -> EmployerStudentContactNode:
        """Employer rejects student response"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            employer = user.employer_profile
            contact = EmployerStudentContact.objects.get(
                id=contact_id,
                employer=employer
            )
        except (EmployerProfile.DoesNotExist, EmployerStudentContact.DoesNotExist):
            raise Exception("Contact not found")
        
        contact.reject()
        return EmployerStudentContactNode.from_model(contact)
    
    @strawberry.mutation
    def save_talent_search(
        self,
        info,
        filters_json_str: str,  # JSON string instead of dict
        search_query: Optional[str] = None,
        saved_profiles: Optional[list[str]] = None
    ) -> TalentPoolSearchNode:
        """Save talent pool search"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            employer = user.employer_profile
        except EmployerProfile.DoesNotExist:
            raise Exception("Employer profile not found")
        
        # Parse JSON string
        import json
        try:
            filters_json = json.loads(filters_json_str)
        except json.JSONDecodeError:
            raise Exception("Invalid filters JSON")
        
        search = TalentPoolSearch.objects.create(
            employer=employer,
            filters_json=filters_json,
            search_query=search_query,
            saved_profiles=saved_profiles or [],
            results_count=len(saved_profiles or []),
            tenant=user.tenant
        )
        
        return TalentPoolSearchNode.from_model(search)
    
    @strawberry.mutation
    def update_dashboard_stats(
        self,
        info
    ) -> EmployerDashboardStatsNode:
        """Update employer dashboard statistics"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            employer = user.employer_profile
        except EmployerProfile.DoesNotExist:
            raise Exception("Employer profile not found")
        
        stats = EmployerDashboardStats.update_stats(employer)
        return EmployerDashboardStatsNode.from_model(stats)
