import strawberry
from .notification_queries import NotificationQueries

@strawberry.type
class LmsNotificationQueries(NotificationQueries):
    pass
