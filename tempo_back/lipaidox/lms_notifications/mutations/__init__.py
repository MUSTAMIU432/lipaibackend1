import strawberry
from .notification_mutations import NotificationMutations

@strawberry.type
class LmsNotificationMutations(NotificationMutations):
    pass
