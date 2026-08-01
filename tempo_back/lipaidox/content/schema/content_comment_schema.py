import strawberry
from typing import Optional
from datetime import datetime


@strawberry.type
class ContentCommentAuthorType:
    id: strawberry.ID
    username: str
    displayName: str
    avatar: Optional[str]
    isVerified: bool


@strawberry.type
class ContentCommentType:
    id: strawberry.ID
    author: ContentCommentAuthorType
    body: str
    status: str
    createdAt: datetime
    updatedAt: datetime


@strawberry.type
class ContentCommentListType:
    items: list[ContentCommentType]
    totalCount: int


@strawberry.type
class CreateContentCommentPayload:
    comment: ContentCommentType


@strawberry.type
class DeleteContentCommentPayload:
    success: bool
