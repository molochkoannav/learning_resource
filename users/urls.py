from django.urls import path

from .views import UserRetrieveUpdateAPIView

urlpatterns = [
    path("profile/", UserRetrieveUpdateAPIView.as_view(), name="profile"),
]
