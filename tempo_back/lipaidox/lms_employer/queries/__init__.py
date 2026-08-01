import strawberry
from .employer_queries import EmployerQueries

@strawberry.type
class LmsEmployerQueries(EmployerQueries):
    pass
