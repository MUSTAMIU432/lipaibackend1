import strawberry
from .message_mutations import MessageMutations

@strawberry.type
class LmsMessageMutations(MessageMutations):
    pass
