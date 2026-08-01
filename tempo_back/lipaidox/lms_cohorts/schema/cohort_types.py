import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.cohort import Cohort, CohortMember, CohortSession

@strawberry.type
class MeetingSchedule:
    days: List[str]
    time: str

@strawberry.type
class CohortMemberNode:
    id: strawberry.ID
    cohortId: strawberry.ID
    studentId: strawberry.ID
    studentName: str
    status: str
    approvedBy: Optional[str]
    approvedAt: Optional[datetime]
    completionPercentage: float
    joinedAt: datetime

    @classmethod
    def from_model(cls, instance: CohortMember):
        return cls(
            id=strawberry.ID(str(instance.id)),
            cohortId=strawberry.ID(str(instance.cohort.id)),
            studentId=strawberry.ID(str(instance.student.id)),
            studentName=instance.student.user.username,
            status=instance.status,
            approvedBy=instance.approved_by.username if instance.approved_by else None,
            approvedAt=instance.approved_at,
            completionPercentage=float(instance.completion_percentage),
            joinedAt=instance.joined_at,
        )

@strawberry.type
class CohortSessionNode:
    id: strawberry.ID
    cohortId: strawberry.ID
    title: str
    description: Optional[str]
    scheduledAt: datetime
    durationMinutes: int
    meetUrl: Optional[str]
    recordingUrl: Optional[str]
    isCancelled: bool
    cancellationReason: Optional[str]
    instructorId: strawberry.ID
    instructorName: str
    createdAt: datetime
    
    # Computed properties
    isPast: bool
    isUpcoming: bool
    attendedBy: List[str]  # List of student names

    @classmethod
    def from_model(cls, instance: CohortSession):
        return cls(
            id=strawberry.ID(str(instance.id)),
            cohortId=strawberry.ID(str(instance.cohort.id)),
            title=instance.title,
            description=instance.description,
            scheduledAt=instance.scheduled_at,
            durationMinutes=instance.duration_minutes,
            meetUrl=instance.meet_url,
            recordingUrl=instance.recording_url,
            isCancelled=instance.is_cancelled,
            cancellationReason=instance.cancellation_reason,
            instructorId=strawberry.ID(str(instance.instructor.id)),
            instructorName=instance.instructor.username,
            createdAt=instance.created_at,
            isPast=instance.is_past,
            isUpcoming=instance.is_upcoming,
            attendedBy=[student.user.username for student in instance.attended_by.all()],
        )

@strawberry.type
class CohortNode:
    id: strawberry.ID
    courseId: strawberry.ID
    courseTitle: str
    instructorId: strawberry.ID
    instructorName: str
    name: str
    description: Optional[str]
    startDate: datetime
    endDate: datetime
    maxStudents: int
    status: str
    isPublic: bool
    requiresApproval: bool
    defaultMeetingUrl: Optional[str]
    meetingSchedule: Optional[MeetingSchedule]
    createdAt: datetime
    updatedAt: datetime
    
    # Computed properties
    currentEnrollment: int
    availableSlots: int
    isFull: bool
    isEnrollmentOpen: bool
    
    # Related data
    members: List[CohortMemberNode]
    sessions: List[CohortSessionNode]

    @classmethod
    def from_model(cls, instance: Cohort, include_members=False, include_sessions=False):
        members = []
        sessions = []
        
        if include_members:
            members = [CohortMemberNode.from_model(member) for member in instance.members.all()]
        
        if include_sessions:
            sessions = [CohortSessionNode.from_model(session) for session in instance.sessions.all()]
        
        # Convert meeting schedule dict to MeetingSchedule object
        meeting_schedule_obj = None
        if instance.meeting_schedule:
            meeting_schedule_obj = MeetingSchedule(
                days=instance.meeting_schedule.get('days', []),
                time=instance.meeting_schedule.get('time', '')
            )
        
        return cls(
            id=strawberry.ID(str(instance.id)),
            courseId=strawberry.ID(str(instance.course.id)),
            courseTitle=instance.course.title,
            instructorId=strawberry.ID(str(instance.instructor.id)),
            instructorName=instance.instructor.username,
            name=instance.name,
            description=instance.description,
            startDate=instance.start_date,
            endDate=instance.end_date,
            maxStudents=instance.max_students,
            status=instance.status,
            isPublic=instance.is_public,
            requiresApproval=instance.requires_approval,
            defaultMeetingUrl=instance.default_meeting_url,
            meetingSchedule=meeting_schedule_obj,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
            currentEnrollment=instance.current_enrollment,
            availableSlots=instance.available_slots,
            isFull=instance.is_full,
            isEnrollmentOpen=instance.is_enrollment_open,
            members=members,
            sessions=sessions,
        )
