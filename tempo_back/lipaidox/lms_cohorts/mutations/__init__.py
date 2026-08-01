import strawberry
from .cohort_mutations import CohortMutations

@strawberry.type
class LmsCohortMutations(CohortMutations):
    pass
