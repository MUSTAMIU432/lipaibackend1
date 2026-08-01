import strawberry
from typing import Optional
from ..schema.cohort_types import CohortNode, CohortMemberNode, CohortSessionNode
from ..models.cohort import (
    Cohort,
    CohortStatus,
    CohortMember,
    CohortMemberStatus,
    CohortSession
)
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class CohortMutations:
    @strawberry.mutation
    def create_cohort(
        self,
        info,
        course_id: strawberry.ID,
        name: str,
        start_date: str,  # ISO datetime string
        end_date: str,    # ISO datetime string
        max_students: int = 30,
        description: Optional[str] = None,
        is_public: bool = True,
        requires_approval: bool = False,
        default_meeting_url: Optional[str] = None
    ) -> CohortNode:
        """Create a new cohort (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is instructor for this course
        from lipaidox.lms_content.models import Course
        course = Course.objects.get(id=course_id)
        
        # Simple instructor check - in production you'd check proper permissions
        if not (user.is_staff or hasattr(user, 'instructor_profile')):
            raise Exception("Only instructors can create cohorts")
        
        from datetime import datetime
        from dateutil.parser import parse
        
        cohort = Cohort.objects.create(
            course=course,
            instructor=user,
            name=name,
            description=description,
            start_date=parse(start_date),
            end_date=parse(end_date),
            max_students=max_students,
            status=CohortStatus.DRAFT,
            is_public=is_public,
            requires_approval=requires_approval,
            default_meeting_url=default_meeting_url,
            tenant=user.tenant
        )
        
        return CohortNode.from_model(cohort)
    
    @strawberry.mutation
    def update_cohort_status(
        self,
        info,
        cohort_id: strawberry.ID,
        status: str
    ) -> CohortNode:
        """Update cohort status"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            cohort = Cohort.objects.get(id=cohort_id)
            
            # Check permissions
            if cohort.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            # Validate status
            try:
                cohort_status = CohortStatus(status)
            except ValueError:
                raise Exception("Invalid status")
            
            cohort.status = cohort_status
            cohort.save()
            
            return CohortNode.from_model(cohort)
        except Cohort.DoesNotExist:
            raise Exception("Cohort not found")
    
    @strawberry.mutation
    def join_cohort(
        self,
        info,
        cohort_id: strawberry.ID
    ) -> CohortMemberNode:
        """Join a cohort (student only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            cohort = Cohort.objects.get(id=cohort_id)
            
            member = cohort.add_student(student)
            return CohortMemberNode.from_model(member)
        except StudentProfile.DoesNotExist:
            raise Exception("Student profile not found")
        except Cohort.DoesNotExist:
            raise Exception("Cohort not found")
    
    @strawberry.mutation
    def approve_cohort_member(
        self,
        info,
        member_id: strawberry.ID
    ) -> CohortMemberNode:
        """Approve a pending cohort member (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            member = CohortMember.objects.get(id=member_id)
            
            # Check permissions
            if member.cohort.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            member.approve(user)
            return CohortMemberNode.from_model(member)
        except CohortMember.DoesNotExist:
            raise Exception("Cohort member not found")
    
    @strawberry.mutation
    def leave_cohort(
        self,
        info,
        cohort_id: strawberry.ID
    ) -> bool:
        """Leave a cohort (student only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            member = CohortMember.objects.get(cohort_id=cohort_id, student=student)
            member.drop()
            return True
        except StudentProfile.DoesNotExist:
            raise Exception("Student profile not found")
        except CohortMember.DoesNotExist:
            raise Exception("Not a member of this cohort")
    
    @strawberry.mutation
    def create_cohort_session(
        self,
        info,
        cohort_id: strawberry.ID,
        title: str,
        scheduled_at: str,  # ISO datetime string
        duration_minutes: int = 60,
        description: Optional[str] = None,
        meet_url: Optional[str] = None
    ) -> CohortSessionNode:
        """Create a new cohort session (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            cohort = Cohort.objects.get(id=cohort_id)
            
            # Check permissions
            if cohort.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            from datetime import datetime
            from dateutil.parser import parse
            
            session = CohortSession.objects.create(
                cohort=cohort,
                instructor=user,
                title=title,
                description=description,
                scheduled_at=parse(scheduled_at),
                duration_minutes=duration_minutes,
                meet_url=meet_url,
                tenant=user.tenant
            )
            
            return CohortSessionNode.from_model(session)
        except Cohort.DoesNotExist:
            raise Exception("Cohort not found")
    
    @strawberry.mutation
    def mark_session_attendance(
        self,
        info,
        session_id: strawberry.ID,
        student_ids: list[strawberry.ID]
    ) -> CohortSessionNode:
        """Mark attendance for a session (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            session = CohortSession.objects.get(id=session_id)
            
            # Check permissions
            if session.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            # Mark attendance
            for student_id in student_ids:
                try:
                    student = StudentProfile.objects.get(id=student_id)
                    session.mark_attendance(student)
                except StudentProfile.DoesNotExist:
                    continue  # Skip invalid student IDs
            
            return CohortSessionNode.from_model(session)
        except CohortSession.DoesNotExist:
            raise Exception("Session not found")
    
    @strawberry.mutation
    def cancel_session(
        self,
        info,
        session_id: strawberry.ID,
        reason: Optional[str] = None
    ) -> CohortSessionNode:
        """Cancel a cohort session (instructor only)"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            session = CohortSession.objects.get(id=session_id)
            
            # Check permissions
            if session.instructor != user and not user.is_staff:
                raise Exception("Permission denied")
            
            session.cancel(reason)
            return CohortSessionNode.from_model(session)
        except CohortSession.DoesNotExist:
            raise Exception("Session not found")
