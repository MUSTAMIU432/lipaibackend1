from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView
from lipaidox_backend.schema import schema as graphql_schema
from lipaidox.auth.jwt_auth import authenticate_request


class JWTGraphQLView(GraphQLView):
    """Extends Strawberry's view to authenticate request.user from Bearer token."""

    def get_context(self, request, response):
        authenticate_request(request)
        return super().get_context(request, response)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql/", csrf_exempt(JWTGraphQLView.as_view(schema=graphql_schema, graphiql=True))),
    path("api/", include("lipaidox.creator_profile.urls")),
    path("payments/", include("lipaidox.payment.urls")),
    path("", include("lipaidox.lost_found.urls")),
]

if settings.DEBUG:
    # Range-aware media serving so mobile <video> gets 206 Partial Content.
    from django.urls import re_path
    from lipaidox_backend.media_serve import ranged_media_serve

    _media_prefix = settings.MEDIA_URL.lstrip("/")
    urlpatterns += [
        re_path(
            rf"^{_media_prefix}(?P<path>.*)$",
            ranged_media_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
