from django.contrib.auth import get_user_model
from rest_framework import serializers

from users.models import Payment



User = get_user_model()




class PaymentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'payment_date', 'payment_method']


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
