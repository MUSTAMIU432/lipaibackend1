import strawberry
from .cohort_queries import CohortQueries

@strawberry.type
class LmsCohortQueries(CohortQueries):
    pass
