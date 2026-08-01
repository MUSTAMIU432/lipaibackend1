import strawberry
from datetime import datetime, timedelta
from typing import List, Optional
from django.db import models
from django.utils import timezone
from ..schema.employer_types import (
    EmployerProfileNode,
    EmployerDashboardStatsNode,
    EmployerStudentContactNode,
    TalentPoolSearchNode
)
from ..models.employer import (
    EmployerProfile,
    TalentPoolSearch,
    EmployerStudentContact,
    EmployerDashboardStats
)
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class EmployerQueries:
    @strawberry.field
    def my_employer_profile(
        self,
        info,
        include_stats: bool = False,
        include_contacts: bool = False,
        include_searches: bool = False
    ) -> Optional[EmployerProfileNode]:
        """Get current user's employer profile"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            profile = user.employer_profile
            return EmployerProfileNode.from_model(
                profile,
                include_stats=include_stats,
                include_contacts=include_contacts,
                include_searches=include_searches
            )
        except EmployerProfile.DoesNotExist:
            return None
    
    @strawberry.field
    def employer_dashboard(self, info) -> Optional[EmployerProfileNode]:
        """Get employer dashboard data"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            profile = user.employer_profile
            return EmployerProfileNode.from_model(
                profile,
                include_stats=True,
                include_contacts=True,
                include_searches=True
            )
        except EmployerProfile.DoesNotExist:
            return None
    
    @strawberry.field
    def my_student_contacts(
        self,
        info,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[EmployerStudentContactNode]:
        """Get employer's student contacts"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            employer = user.employer_profile
            contacts = employer.student_contacts.all()
            
            if status:
                contacts = contacts.filter(status=status)
            
            contacts = contacts.order_by('-created_at')[:limit]
            return [EmployerStudentContactNode.from_model(contact) for contact in contacts]
        except EmployerProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_talent_searches(
        self,
        info,
        limit: int = 20
    ) -> List[TalentPoolSearchNode]:
        """Get employer's talent pool searches"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            employer = user.employer_profile
            searches = employer.talent_searches.order_by('-searched_at')[:limit]
            return [TalentPoolSearchNode.from_model(search) for search in searches]
        except EmployerProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def search_talent_pool(
        self,
        info,
        filters_json_str: str,  # JSON string instead of dict
        search_query: Optional[str] = None,
        limit: int = 50
    ) -> List[str]:
        """Search talent pool with filters - returns student IDs"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            employer = user.employer_profile
        except EmployerProfile.DoesNotExist:
            return []
        
        # Parse JSON string
        import json
        try:
            filters_json = json.loads(filters_json_str)
        except json.JSONDecodeError:
            return []
        
        # Build query based on filters
        students = StudentProfile.objects.all()
        
        # Apply filters
        if 'skills' in filters_json:
            skills = filters_json['skills']
            if skills:
                students = students.filter(skills__name__in=skills).distinct()
        
        if 'education_level' in filters_json:
            education_level = filters_json['education_level']
            if education_level:
                students = students.filter(education_records__degree_type__in=education_level).distinct()
        
        if 'experience_years' in filters_json:
            exp_years = filters_json['experience_years']
            if exp_years:
                students = students.filter(workexperience__years_of_experience__gte=exp_years).distinct()
        
        if 'location' in filters_json:
            location = filters_json['location']
            if location:
                students = students.filter(location__icontains=location)
        
        if 'search_query' in filters_json or search_query:
            query = search_query or filters_json.get('search_query', '')
            if query:
                students = students.filter(
                    models.Q(user__username__icontains=query) |
                    models.Q(user__email__icontains=query) |
                    models.Q(bio__icontains=query)
                ).distinct()
        
        # Get total count
        total_count = students.count()
        
        # Limit results
        students = students[:limit]
        
        # Convert to list of student IDs
        student_ids = [str(student.id) for student in students]
        
        # Save search to history
        TalentPoolSearch.objects.create(
            employer=employer,
            filters_json=filters_json,
            search_query=search_query,
            results_count=total_count,
            saved_profiles=student_ids,
            tenant=user.tenant
        )
        
        return student_ids
    
    @strawberry.field
    def employer_contact_detail(
        self,
        info,
        contact_id: strawberry.ID
    ) -> Optional[EmployerStudentContactNode]:
        """Get detailed contact information"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            employer = user.employer_profile
            contact = EmployerStudentContact.objects.get(
                id=contact_id,
                employer=employer
            )
            return EmployerStudentContactNode.from_model(contact)
        except (EmployerProfile.DoesNotExist, EmployerStudentContact.DoesNotExist):
            return None
    
    @strawberry.field
    def my_dashboard_stats(self, info) -> Optional[EmployerDashboardStatsNode]:
        """Get employer dashboard statistics"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            employer = user.employer_profile
            stats, created = EmployerDashboardStats.objects.get_or_create(
                employer=employer,
                defaults={
                    'stats_period_start': timezone.now() - timedelta(days=30),
                    'stats_period_end': timezone.now(),
                }
            )
            
            # Update stats if needed
            if created or (timezone.now() - stats.updated_at).days > 1:
                stats = EmployerDashboardStats.update_stats(employer)
            
            return EmployerDashboardStatsNode.from_model(stats)
        except (EmployerProfile.DoesNotExist):
            return None
