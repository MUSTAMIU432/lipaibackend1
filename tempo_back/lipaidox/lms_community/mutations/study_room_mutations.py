import strawberry
from typing import Optional
from ..schema.study_room_types import StudyRoomNode
from ..models.study_room import StudyRoom, StudyRoomMember, RoomType, MemberRole
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class StudyRoomMutations:
    @strawberry.mutation
    def create_study_room(
        self,
        info,
        name: str,
        slug: str,
        description: Optional[str] = None,
        room_type: str = "public",
        max_members: int = 50,
        course_id: Optional[strawberry.ID] = None
    ) -> StudyRoomNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        room = StudyRoom.objects.create(
            name=name,
            slug=slug,
            description=description,
            room_type=room_type,
            max_members=max_members,
            course_id=course_id,
            creator=user,
            tenant=user.tenant
        )
        
        # Add creator as owner
        student = StudentProfile.objects.get(user=user)
        StudyRoomMember.objects.create(
            room=room, 
            student=student, 
            role=MemberRole.OWNER
        )
        
        return StudyRoomNode.from_model(room)

    @strawberry.mutation
    def join_study_room(self, info, room_id: strawberry.ID) -> StudyRoomNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        room = StudyRoom.objects.get(id=room_id)
        
        # Check if room is active and has space
        if not room.is_active:
            raise Exception("Room is not active")
        
        current_members = room.members.count()
        if current_members >= room.max_members:
            raise Exception("Room is full")
        
        StudyRoomMember.objects.get_or_create(
            room=room, 
            student=student,
            defaults={'role': MemberRole.MEMBER}
        )
        return StudyRoomNode.from_model(room)

    @strawberry.mutation
    def leave_study_room(self, info, room_id: strawberry.ID) -> bool:
        user = info.context.request.user
        StudyRoomMember.objects.filter(room_id=room_id, student__user=user).delete()
        return True

    @strawberry.mutation
    def update_member_role(
        self, 
        info, 
        room_id: strawberry.ID, 
        member_id: strawberry.ID, 
        role: str
    ) -> StudyRoomNode:
        user = info.context.request.user
        
        # Check if requester is owner
        requester_member = StudyRoomMember.objects.get(
            room_id=room_id, 
            student__user=user,
            role=MemberRole.OWNER
        )
        
        member = StudyRoomMember.objects.get(id=member_id)
        member.role = role
        member.save()
        
        return StudyRoomNode.from_model(requester_member.room)

    @strawberry.mutation
    def update_online_status(self, info, room_id: strawberry.ID, is_online: bool) -> bool:
        user = info.context.request.user
        member = StudyRoomMember.objects.get(
            room_id=room_id, 
            student__user=user
        )
        member.is_online = is_online
        if is_online:
            from django.utils import timezone
            member.last_seen = timezone.now()
        member.save()
        return True
