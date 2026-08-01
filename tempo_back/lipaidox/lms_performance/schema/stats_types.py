import strawberry

@strawberry.type
class PerformanceStatsNode:
    totalHours: float
    completionRate: float
    currentStreak: int
    totalAssessments: int
    averageScore: float
