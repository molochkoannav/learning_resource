from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny
from users.apps import UsersConfig
from .views import (
    PaymentViewSet,
    RegisterView,
    UserRetrieveUpdateAPIView,
    UserViewSet,
)

app_name = UsersConfig.name

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
   
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(permission_classes=[AllowAny]), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(permission_classes=[AllowAny]), name="token_refresh"),
    path("profile/", UserRetrieveUpdateAPIView.as_view(), name="profile"),
    path("", include(router.urls)),
]