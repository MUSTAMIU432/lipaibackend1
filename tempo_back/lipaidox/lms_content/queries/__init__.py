import strawberry
from .course_queries import CourseQueries
from .lesson_queries import LessonQueries
from .lab_queries import LabQueries
from .section_queries import SectionQueries
from .resource_queries import ResourceQueries
from .dashboard_queries import DashboardQueries

@strawberry.type
class ContentQueries(
    CourseQueries,
    LessonQueries,
    LabQueries,
    SectionQueries,
    ResourceQueries,
    DashboardQueries
):
    pass
