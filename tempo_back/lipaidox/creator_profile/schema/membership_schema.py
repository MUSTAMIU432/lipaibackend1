import strawberry
from typing import Optional
from datetime import datetime


@strawberry.type
class SubscriberUserType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool
    isCreator: bool


@strawberry.type
class SubscriberListType:
    users: list[SubscriberUserType]
    totalCount: int


@strawberry.type
class CreatorSummaryType:
    userId: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool


@strawberry.type
class MembershipItemType:
    id: strawberry.ID
    status: str
    notificationPreference: str
    createdAt: datetime
    creator: CreatorSummaryType


@strawberry.type
class MembershipListType:
    items: list[MembershipItemType]
    totalCount: int


@strawberry.type
class SubscriptionStatusResult:
    isSubscribed: bool
    subscriberCount: int
    status: Optional[str] = None
    notificationPreference: Optional[str] = None


@strawberry.type
class SubscribeFreePayload:
    isSubscribed: bool
    status: str
    subscriberCount: int
    notificationPreference: str


@strawberry.type
class UnsubscribePayload:
    isSubscribed: bool
    subscriberCount: int


@strawberry.type
class UpdateNotificationPreferencePayload:
    isSubscribed: bool
    notificationPreference: str
