import strawberry
from typing import Optional, List
from ..schema.conversation_types import ConversationNode
from ..schema.message_types import MessageNode
from ..models.conversation import Conversation
from ..models.message import Message, MessageType
from ..models.attachment import MessageAttachment
from lipaidox.lms_identity.models import StudentProfile
from lipaidox.lms_content.models import Course

@strawberry.type
class MessageMutations:
    @strawberry.mutation
    def send_message(
        self,
        info,
        conversation_id: strawberry.ID,
        content: str,
        message_type: str = "text"
    ) -> MessageNode:
        """Send a message in a conversation"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Check if user can participate in this conversation
        if not conversation.can_participate(user):
            raise Exception("You cannot participate in this conversation")
        
        # Check if conversation is active
        if not conversation.is_active:
            raise Exception("Conversation has ended")
        
        message = Message.create_message(
            conversation=conversation,
            sender=user,
            content=content,
            message_type=message_type
        )
        
        return MessageNode.from_model(message)
    
    @strawberry.mutation
    def start_conversation(
        self,
        info,
        course_id: strawberry.ID,
        instructor_id: strawberry.ID,
        initial_message: str
    ) -> ConversationNode:
        """Start a new conversation with an instructor"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is a student
        try:
            student = user.student_profile
        except StudentProfile.DoesNotExist:
            raise Exception("Only students can start conversations")
        
        # Get course and instructor
        course = Course.objects.get(id=course_id)
        from lipaidox_auth.models import User
        instructor = User.objects.get(id=instructor_id)
        
        # Check if student is enrolled in the course
        if not course.enrollments.filter(student=student).exists():
            raise Exception("You must be enrolled in this course to start a conversation")
        
        # Create or get conversation
        conversation, created = Conversation.get_or_create_conversation(
            course=course,
            student=student,
            instructor=instructor
        )
        
        # Send initial message if this is a new conversation
        if created:
            Message.create_message(
                conversation=conversation,
                sender=user,
                content=initial_message
            )
        
        return ConversationNode.from_model(conversation, user=user)
    
    @strawberry.mutation
    def mark_messages_read(
        self,
        info,
        conversation_id: strawberry.ID
    ) -> int:
        """Mark all messages in a conversation as read"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Check if user can participate in this conversation
        if not conversation.can_participate(user):
            raise Exception("You cannot participate in this conversation")
        
        # Mark messages as read
        count = Message.mark_conversation_read(conversation, user)
        return count
    
    @strawberry.mutation
    def end_conversation(
        self,
        info,
        conversation_id: strawberry.ID
    ) -> ConversationNode:
        """End a conversation"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Check if user can participate in this conversation
        if not conversation.can_participate(user):
            raise Exception("You cannot participate in this conversation")
        
        # End the conversation
        conversation.end_conversation(ended_by=user)
        
        return ConversationNode.from_model(conversation, user=user)
