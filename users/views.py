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
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
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


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class UserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["paid_course", "paid_lesson", "payment_method"]
    ordering_fields = ["date_payment"]
    ordering = ["-date_payment"]


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


# ---------- helpers ----------

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


# ---------- views ----------

@csrf_exempt
@require_POST
def create_payment_view(request):
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

    # --- 2. Пользователь ---
    user = request.user if request.user.is_authenticated else None
    if user is None:
        from users.models import CustomUser
        user_id = body.get("user_id")
        if not user_id:
            return JsonResponse({"error": "user_id is required"}, status=400)
        user = get_object_or_404(CustomUser, id=user_id)

    # --- 3. Что оплачиваем ---
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

    # --- 4. Валидация суммы ДО Stripe ---
    if amount is None or float(amount) <= 0:
        return JsonResponse({"error": "Invalid amount for this item"}, status=400)

    # --- 5. Наличные ---
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

    # --- 6. Карта: Product -> Price -> Payment -> Session ---
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

        # Payment создаём ТОЛЬКО после успешных Product + Price
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
    payment = get_object_or_404(Payment, stripe_session_id=session_id)

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

    # Stripe отдаёт "paid"/"unpaid"/"no_payment_required" — маппим в локальные статусы
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