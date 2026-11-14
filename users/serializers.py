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
    payments = PaymentShortSerializer(many=True, read_only=True)    

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
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user