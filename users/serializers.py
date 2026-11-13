from django.contrib.auth import get_user_model
from rest_framework import serializers
from users.models import Payment



User = get_user_model()




class PaymentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'date_payment', 'payment_method']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    payments = PaymentShortSerializer(source='payments', many=True, read_only=True)    
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
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
        }

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    class Meta:
        model = User
        fields = ("id", "email", "password")

    def create(self, validated_data):
      
        user = User.objects.create_user(
            id=validated_data['id'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user