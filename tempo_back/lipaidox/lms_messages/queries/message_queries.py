import strawberry
from typing import List, Optional
from ..schema.conversation_types import ConversationNode
from ..schema.message_types import MessageNode
from ..models.conversation import Conversation
from ..models.message import Message

@strawberry.type
class MessageQueries:
    @strawberry.field
    def my_conversations(self, info) -> List[ConversationNode]:
        """Get all conversations for the current user"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        conversations = []
        
        # Check if user is a student
        if hasattr(user, 'student_profile'):
            student_conversations = Conversation.get_student_conversations(user.student_profile)
            for conv in student_conversations:
                conversations.append(ConversationNode.from_model(conv, user=user))
        
        # Check if user is an instructor
        instructor_conversations = Conversation.get_instructor_conversations(user)
        for conv in instructor_conversations:
            conversations.append(ConversationNode.from_model(conv, user=user))
        
        return conversations
    
    @strawberry.field
    def conversation_messages(
        self,
        info,
        conversation_id: strawberry.ID,
        limit: int = 50
    ) -> List[MessageNode]:
        """Get messages in a conversation"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        conversation = Conversation.objects.get(id=conversation_id)
        
        # Check if user can participate in this conversation
        if not conversation.can_participate(user):
            raise Exception("You cannot view this conversation")
        
        messages = Message.get_conversation_messages(conversation, limit=limit)
        return [MessageNode.from_model(msg) for msg in messages]
    
    @strawberry.field
    def conversation_detail(
        self,
        info,
        conversation_id: strawberry.ID
    ) -> Optional[ConversationNode]:
        """Get conversation details"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            
            # Check if user can participate in this conversation
            if not conversation.can_participate(user):
                return None
            
            return ConversationNode.from_model(conversation, user=user)
        except Conversation.DoesNotExist:
            return None
    
    @strawberry.field
    def unread_conversations_count(self, info) -> int:
        """Get count of conversations with unread messages"""
        user = info.context.request.user
        if not user.is_authenticated:
            return 0
        
        conversations = []
        
        # Check if user is a student
        if hasattr(user, 'student_profile'):
            conversations = Conversation.get_student_conversations(user.student_profile)
        
        # Check if user is an instructor
        else:
            conversations = Conversation.get_instructor_conversations(user)
        
        # Count conversations with unread messages
        unread_count = 0
        for conv in conversations:
            if Message.get_unread_count(conv, user) > 0:
                unread_count += 1
        
        return unread_count
