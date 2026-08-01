import strawberry
from .performance_queries import PerformanceQueries
from .streak_queries import StreakQueries

@strawberry.type
class PerformanceQueries(
    PerformanceQueries,
    StreakQueries
):
    pass
