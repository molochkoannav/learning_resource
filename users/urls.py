from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import PaymentViewSet, UserRetrieveUpdateAPIView

from users.apps import UsersConfig

app_name = UsersConfig.name

router = SimpleRouter()
router.register("payments", PaymentViewSet)

urlpatterns = [
    path("profile/", UserRetrieveUpdateAPIView.as_view(), name="profile"),
]
