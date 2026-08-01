import strawberry
from .message_queries import MessageQueries

@strawberry.type
class LmsMessageQueries(MessageQueries):
    pass
