from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    validate_password as django_validate_password,
)
from rest_framework import serializers

from users.models import Payment

User = get_user_model()


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class PaymentShortSerializer(serializers.ModelSerializer):
    """Лёгкая вложенная репрезентация платежа (только чтение)."""

    class Meta:
        model = Payment
        fields = ["id", "amount", "date_payment", "payment_method"]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    """
    Платёж — только чтение.

    Создание платежа идёт через create_payment_view (там сервер сам считает
    amount, ставит user=request.user и заполняет Stripe-поля), а смена статуса —
    через вебхук / check_payment_status_view. Поэтому любые попытки PATCH/POST
    с amount/user/status/stripe_* должны быть невозможны даже на уровне
    сериализатора (defence-in-depth: если кто-то снова включит ModelViewSet,
    это не превратится в дыру).
    """

    class Meta:
        model = Payment
        fields = (
            "id",
            "user",
            "paid_course",
            "paid_lesson",
            "amount",
            "currency",
            "payment_method",
            "status",
            "stripe_product_id",
            "stripe_price_id",
            "stripe_session_id",
            "payment_url",
            "date_payment",
        )
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    payments = PaymentShortSerializer(many=True, read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        qs = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )
        return value

    def validate_password(self, value):
        # Django-валидаторы (длина, общие пароли, similarity, цифры)
        django_validate_password(value, self.instance)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "avatar_image",
            "phone_number",
            "city",
            "password",
            "payments",
        )
        # is_staff / is_superuser / is_active / date_joined НЕ включены —
        # значит PATCH через /users/<id>/ не может повысить привилегии.
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "email": {"required": True},
        }


class UserListSerializer(serializers.ModelSerializer):
    """
    Для staff-листинга: без вложенных платежей и без password,
    чтобы не тянуть N+1 и не отдавать PII сверх необходимого.
    """

    class Meta:
        model = User
        fields = ("id", "email", "phone_number", "city")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )
        return value

    def validate_password(self, value):
        django_validate_password(value)
        return value

    class Meta:
        model = User
        fields = ("id", "email", "password")
        read_only_fields = ("id",)

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )