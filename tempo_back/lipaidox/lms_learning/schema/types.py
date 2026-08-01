import strawberry
from typing import List, Optional
from datetime import datetime
from ..models import Enrollment, LessonProgress, Note, Wishlist

@strawberry.type
class EnrollmentNode:
    id: strawberry.ID
    courseId: strawberry.ID
    status: str
    progressPercent: int
    enrolledAt: datetime
    lastAccessed: datetime

@strawberry.type
class LessonProgressNode:
    id: strawberry.ID
    lessonId: strawberry.ID
    watchTimeSeconds: int
    lastPositionSeconds: int
    isCompleted: bool
    completedAt: Optional[datetime]

@strawberry.type
class LessonNoteNode:
    id: strawberry.ID
    lessonId: strawberry.ID
    content: str
    timestampSeconds: int
    createdAt: datetime

@strawberry.type
class WishlistNode:
    id: strawberry.ID
    courseId: strawberry.ID
    savedAt: datetime
