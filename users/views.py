from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Payment
from .serializers import PaymentSerializer, RegisterSerializer, UserSerializer
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from materials.models import Course, Lesson   
from .models import Payment                    
from .services import create_stripe_product, create_stripe_price, create_checkout_session, retrieve_checkout_session

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """Полный CRUD для пользователей"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class UserRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    """Просмотр и редактирование СВОЕГО профиля: /users/me/"""

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



@csrf_exempt
@require_POST
def create_payment_view(request):
    """
    Ожидает POST-запрос с телом:
    {
        "payment_method": "card" | "cash",
        "course_id": 1,       # либо course_id,
        "lesson_id": null     # либо lesson_id
    }
    """
    # --- 1. Тело запроса ---
    body = json.loads(request.body)
    payment_method = body.get("payment_method", "card")
    course_id = body.get("course_id")
    lesson_id = body.get("lesson_id")

    if not course_id and not lesson_id:
        return JsonResponse(
            {"error": "course_id or lesson_id is required"}, status=400
        )

    # --- 2. Получаем пользователя ---
    user = request.user if request.user.is_authenticated else None
    if user is None:
        from users.models import CustomUser
        user_id = body.get("user_id")
        if not user_id:
            return JsonResponse({"error": "user_id is required"}, status=400)
        user = get_object_or_404(CustomUser, id=user_id)

    # --- 3. Определяем, что оплачиваем ---
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

    # --- 4. Ветка "наличные" ---
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

    # --- 5. Ветка "карта"---
    if payment_method != "card":
        return JsonResponse({"error": "Unknown payment_method"}, status=400)

    # 5.1. Продукт в Stripe
    product_id = create_stripe_product(
        name=product_name,
        description=f"Оплата: {product_name}",
    )

    # 5.2. Цена в Stripe — передаём float из Decimal
    price_id = create_stripe_price(
        product_id=product_id,
        amount=float(amount),
        currency="rub",
    )

    # 5.3. Запись о платеже
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

    # 5.4. URL возврата
    success_url = request.build_absolute_uri(reverse("payment_success"))
    cancel_url = request.build_absolute_uri(reverse("payment_cancel"))

    # 5.5. Сессия Checkout
    session_data = create_checkout_session(
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"payment_id": payment.id},
    )

    # 5.6. Сохраняем session_id и payment_url
    payment.stripe_session_id = session_data["session_id"]
    payment.payment_url = session_data["payment_url"]
    payment.save(update_fields=["stripe_session_id", "payment_url"])

    # 5.7. Отдаём пользователю ссылку
    return JsonResponse(
        {
            "payment_id": payment.id,
            "payment_url": payment.payment_url,
            "amount": str(payment.amount),
            "message": "Перейдите по ссылке для оплаты",
        },
        status=201,
    )

def check_payment_status_view(request, session_id):
    payment = get_object_or_404(Payment, stripe_session_id=session_id)
    stripe_data = retrieve_checkout_session(session_id)
    payment.status = stripe_data["payment_status"]
    payment.save(update_fields=["status"])

    return JsonResponse({
        "payment_id": payment.id,
        "user_id": payment.user_id,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "stripe_session_id": session_id,
    })

def payment_success_view(request):
    return JsonResponse({"message": "Оплата прошла успешно"})

def payment_cancel_view(request):
    return JsonResponse({"message": "Оплата отменена"})