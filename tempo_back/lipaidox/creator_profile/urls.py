from django.urls import path
from . import views

urlpatterns = [
    path("upload/profile-photo/", views.upload_profile_photo, name="upload_profile_photo"),
    path("upload/content-media/", views.upload_content_media, name="upload_content_media"),
]
