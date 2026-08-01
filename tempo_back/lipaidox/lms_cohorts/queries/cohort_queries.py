import strawberry
from typing import List, Optional
from ..schema.cohort_types import CohortNode, CohortMemberNode, CohortSessionNode
from ..models.cohort import Cohort, CohortMember, CohortSession

@strawberry.type
class CohortQueries:
    @strawberry.field
    def my_cohorts(self, info) -> List[CohortNode]:
        """Get cohorts for current user (as student or instructor)"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        cohorts = []
        
        # As instructor
        instructor_cohorts = Cohort.objects.filter(instructor=user)
        for cohort in instructor_cohorts:
            cohorts.append(CohortNode.from_model(cohort, include_members=True, include_sessions=True))
        
        # As student
        try:
            student = user.student_profile
            student_cohorts = Cohort.objects.filter(members__student=student).distinct()
            for cohort in student_cohorts:
                cohorts.append(CohortNode.from_model(cohort, include_members=False, include_sessions=True))
        except:
            pass  # User is not a student
        
        return cohorts
    
    @strawberry.field
    def available_cohorts(self, info) -> List[CohortNode]:
        """Get cohorts available for student to join"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            student = user.student_profile
            available = Cohort.get_available_cohorts(student)
            return [CohortNode.from_model(cohort) for cohort in available]
        except:
            return []  # User is not a student
    
    @strawberry.field
    def cohort_detail(
        self,
        info,
        cohort_id: strawberry.ID,
        include_members: bool = False,
        include_sessions: bool = False
    ) -> Optional[CohortNode]:
        """Get detailed information about a specific cohort"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            cohort = Cohort.objects.get(id=cohort_id)
            
            # Check access permissions
            # Instructors can see their own cohorts
            if cohort.instructor == user:
                return CohortNode.from_model(cohort, include_members=True, include_sessions=True)
            
            # Students can see cohorts they're members of
            try:
                if cohort.members.filter(student__user=user).exists():
                    return CohortNode.from_model(cohort, include_members=False, include_sessions=True)
            except:
                pass
            
            # Public cohorts can be viewed by anyone enrolled in the course
            if cohort.is_public:
                try:
                    student = user.student_profile
                    if cohort.course.enrollments.filter(student=student).exists():
                        return CohortNode.from_model(cohort, include_members=False, include_sessions=False)
                except:
                    pass
            
            return None
        except Cohort.DoesNotExist:
            return None
    
    @strawberry.field
    def cohort_members(
        self,
        info,
        cohort_id: strawberry.ID
    ) -> List[CohortMemberNode]:
        """Get members of a cohort (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            cohort = Cohort.objects.get(id=cohort_id)
            
            # Check permissions
            if cohort.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            members = cohort.members.all()
            return [CohortMemberNode.from_model(member) for member in members]
        except Cohort.DoesNotExist:
            return []
    
    @strawberry.field
    def cohort_sessions(
        self,
        info,
        cohort_id: strawberry.ID,
        upcoming_only: bool = False
    ) -> List[CohortSessionNode]:
        """Get sessions for a cohort"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            cohort = Cohort.objects.get(id=cohort_id)
            
            # Check access permissions
            if not (cohort.instructor == user or 
                   cohort.members.filter(student__user=user).exists() or
                   user.is_staff):
                return []
            
            sessions = cohort.sessions.all()
            if upcoming_only:
                from django.utils import timezone
                sessions = sessions.filter(scheduled_at__gt=timezone.now(), is_cancelled=False)
            
            return [CohortSessionNode.from_model(session) for session in sessions]
        except Cohort.DoesNotExist:
            return []
    
    @strawberry.field
    def session_detail(
        self,
        info,
        session_id: strawberry.ID
    ) -> Optional[CohortSessionNode]:
        """Get detailed information about a specific session"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            session = CohortSession.objects.get(id=session_id)
            
            # Check access permissions
            if not (session.instructor == user or 
                   session.cohort.members.filter(student__user=user).exists() or
                   user.is_staff):
                return None
            
            return CohortSessionNode.from_model(session)
        except CohortSession.DoesNotExist:
            return None
    
    @strawberry.field
    def my_pending_memberships(self, info) -> List[CohortMemberNode]:
        """Get pending cohort memberships for current student"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            student = user.student_profile
            pending_memberships = CohortMember.objects.filter(
                student=student,
                status=CohortMemberStatus.PENDING
            )
            return [CohortMemberNode.from_model(member) for member in pending_memberships]
        except:
            return []  # User is not a student
