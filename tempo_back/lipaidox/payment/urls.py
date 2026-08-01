"""REST routes for the async payment gateway (webhook + status poll)."""
from django.urls import path

from . import rest_views

urlpatterns = [
    path("callback/<str:gateway>/", rest_views.gateway_callback, name="gateway-callback"),
    path("status/<str:order_reference>/", rest_views.gateway_status, name="gateway-status"),
]
