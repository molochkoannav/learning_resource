from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny
from users.apps import UsersConfig
from . import views

app_name = UsersConfig.name

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("payments", views.PaymentViewSet, basename="payment")

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "login/",
        TokenObtainPairView.as_view(permission_classes=[AllowAny]),
        name="login",
    ),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(permission_classes=[AllowAny]),
        name="token_refresh",
    ),
    path("profile/", views.UserRetrieveUpdateAPIView.as_view(), name="profile"),
    path("", include(router.urls)),
     path("pay/", views.create_payment_view, name="create_payment"),
    path("payment/success/", views.payment_success_view, name="payment_success"),
    path("payment/cancel/", views.payment_cancel_view, name="payment_cancel"),
    path("payment/status/<str:session_id>/", views.check_payment_status_view, name="check_payment_status"),
]
