from django.urls import path
from .views import UserProfileUpdateView


urlpatterns = [
        path('profile/', UserProfileUpdateView.as_view(), name='profile_user'),
]


