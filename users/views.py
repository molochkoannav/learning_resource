import json
import logging

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from materials.models import Course, Lesson
from .models import Payment
from .serializers import PaymentSerializer, RegisterSerializer, UserSerializer
from .services import (
    create_checkout_session,
    create_stripe_price,
    create_stripe_product,
    retrieve_checkout_session,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserViewSet(
    mixins.ListModelMixin,        # список — только staff
    mixins.RetrieveModelMixin,    # свой профиль (или любой — staff)
    mixins.UpdateModelMixin,      # свой профиль (или любой — staff)
    mixins.DestroyModelMixin,     # удаление — только staff
    viewsets.GenericViewSet,
):
    """
    Безопасный CRUD по пользователям.

    - create отсутствует: регистрация только через RegisterView.
    - list / destroy: только администратор (IsAdminUser).
    - retrieve / update: обычный пользователь видит и меняет ТОЛЬКО себя,
      staff — любого. Чужой id → 404 (не 403), чтобы не палить существование.
    """

    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ("list", "destroy"):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.prefetch_related("payments")
        if user.is_staff:
            return qs
        return qs.filter(pk=user.pk)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied(
                "Удаление пользователей доступно только администратору"
            )
        instance.delete()


class UserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    """Эндпоинт /me/ — только свой профиль."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Payments (read-only + фильтр по владельцу)
# ---------------------------------------------------------------------------

class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Только чтение. Создание — через create_payment_view,
    обновление статуса — через вебхук / check_payment_status_view.

    Обычный пользователь видит только СВОИ платежи.
    Чужой id → 404.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["paid_course", "paid_lesson", "payment_method"]
    ordering_fields = ["date_payment"]
    ordering = ["-date_payment"]

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related("user", "paid_course", "paid_lesson")
        if user.is_staff:
            return qs
        return qs.filter(user=user)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "user": serializer.data,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _stripe_error_response(exc: stripe.error.StripeError, payment=None):
    """Единый ответ на ошибки Stripe + пометка «висячего» платежа."""
    logger.exception("Stripe error in payment flow")
    if payment is not None:
        payment.status = "failed"
        payment.save(update_fields=["status"])
    return JsonResponse(
        {
            "error": "Не удалось создать оплату",
            "detail": str(getattr(exc, "user_message", None) or exc),
        },
        status=502,
    )


# ---------------------------------------------------------------------------
# payment flow
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def create_payment_view(request):
    # --- 0. Только аутентифицированные; user_id из тела НЕ принимаем ---
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    user = request.user

    # --- 1. Тело запроса ---
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    payment_method = body.get("payment_method", "card")
    course_id = body.get("course_id")
    lesson_id = body.get("lesson_id")

    if not course_id and not lesson_id:
        return JsonResponse(
            {"error": "course_id or lesson_id is required"}, status=400
        )
    if payment_method not in ("card", "cash"):
        return JsonResponse({"error": "Unknown payment_method"}, status=400)

    # --- 2. Что оплачиваем ---
    if course_id:
        paid_object = get_object_or_404(Course, id=course_id)
        paid_course, paid_lesson = paid_object, None
        amount = paid_object.price_course
        product_name = paid_object.name
    else:
        paid_object = get_object_or_404(Lesson, id=lesson_id)
        paid_course, paid_lesson = None, paid_object
        amount = paid_object.price
        product_name = paid_object.name

    # --- 3. Валидация суммы ДО Stripe ---
    if amount is None or float(amount) <= 0:
        return JsonResponse({"error": "Invalid amount for this item"}, status=400)

    # --- 4. Наличные ---
    if payment_method == "cash":
        payment = Payment.objects.create(
            user=user,
            paid_course=paid_course,
            paid_lesson=paid_lesson,
            amount=amount,
            payment_method="cash",
            status="created",
        )
        return JsonResponse(
            {
                "payment_id": payment.id,
                "message": "Оплата наличными. Ожидайте подтверждения.",
            },
            status=201,
        )

    # --- 5. Карта: Product -> Price -> Payment -> Session ---
    payment = None
    try:
        product_id = create_stripe_product(
            name=product_name,
            description=f"Оплата: {product_name}",
        )
        price_id = create_stripe_price(
            product_id=product_id,
            amount=float(amount),
            currency="rub",
        )

        payment = Payment.objects.create(
            user=user,
            paid_course=paid_course,
            paid_lesson=paid_lesson,
            amount=amount,
            payment_method="card",
            stripe_product_id=product_id,
            stripe_price_id=price_id,
            currency="rub",
            status="created",
        )

        success_url = request.build_absolute_uri(reverse("users:payment_success"))
        cancel_url = request.build_absolute_uri(reverse("users:payment_cancel"))

        session_data = create_checkout_session(
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"payment_id": payment.id},
        )

        payment.stripe_session_id = session_data["session_id"]
        payment.payment_url = session_data["payment_url"]
        payment.save(update_fields=["stripe_session_id", "payment_url"])

        return JsonResponse(
            {
                "payment_id": payment.id,
                "payment_url": payment.payment_url,
                "amount": str(payment.amount),
                "message": "Перейдите по ссылке для оплаты",
            },
            status=201,
        )

    except stripe.error.StripeError as exc:
        return _stripe_error_response(exc, payment=payment)


def check_payment_status_view(request, session_id):
    # --- 0. Только аутентифицированные ---
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    # --- 1. Фильтр по владельцу (staff видит все) ---
    qs = Payment.objects.filter(stripe_session_id=session_id)
    if not request.user.is_staff:
        qs = qs.filter(user=request.user)
    payment = get_object_or_404(qs)  # чужой session_id → 404

    # --- 2. Запрос в Stripe ---
    try:
        stripe_data = retrieve_checkout_session(session_id)
    except stripe.error.StripeError as exc:
        logger.exception("Stripe error in check_payment_status_view")
        return JsonResponse(
            {
                "error": "Не удалось получить статус оплаты",
                "detail": str(getattr(exc, "user_message", None) or exc),
            },
            status=502,
        )

    # --- 3. Маппинг статуса ---
    stripe_status = stripe_data["payment_status"]
    payment.status = {
        "paid": "paid",
        "unpaid": "created",
        "no_payment_required": "paid",
    }.get(stripe_status, payment.status)
    payment.save(update_fields=["status"])

    return JsonResponse(
        {
            "payment_id": payment.id,
            "user_id": payment.user_id,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "stripe_payment_status": stripe_status,
            "stripe_session_id": session_id,
        }
    )


def payment_success_view(request):
    return JsonResponse({"message": "Оплата прошла успешно"})


def payment_cancel_view(request):
    return JsonResponse({"message": "Оплата отменена"})