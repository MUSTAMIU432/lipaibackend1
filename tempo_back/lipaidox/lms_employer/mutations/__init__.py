import strawberry
from .employer_mutations import EmployerMutations

@strawberry.type
class LmsEmployerMutations(EmployerMutations):
    pass
