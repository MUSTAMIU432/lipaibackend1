import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.study_room import StudyRoom, StudyRoomMember
from lipaidox.lms_content.schema.course_types import CourseNode

@strawberry.type
class StudyRoomMemberNode:
    id: strawberry.ID
    username: str
    role: str
    joinedAt: datetime
    isOnline: bool
    lastSeen: Optional[datetime]

    @classmethod
    def from_model(cls, instance: StudyRoomMember):
        return cls(
            id=strawberry.ID(str(instance.id)),
            username=instance.student.user.username,
            role=instance.role,
            joinedAt=instance.joined_at,
            isOnline=instance.is_online,
            lastSeen=instance.last_seen,
        )

@strawberry.type
class StudyRoomNode:
    id: strawberry.ID
    name: str
    description: Optional[str]
    slug: str
    roomType: str
    maxMembers: int
    isActive: bool
    createdAt: datetime
    creatorUsername: str
    course: Optional[CourseNode]
    members: List[StudyRoomMemberNode]

    @classmethod
    def from_model(cls, instance: StudyRoom):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            description=instance.description,
            slug=instance.slug,
            roomType=instance.room_type,
            maxMembers=instance.max_members,
            isActive=instance.is_active,
            createdAt=instance.created_at,
            creatorUsername=instance.creator.username,
            course=CourseNode.from_model(instance.course) if instance.course else None,
            members=[StudyRoomMemberNode.from_model(m) for m in instance.members.all()],
        )
