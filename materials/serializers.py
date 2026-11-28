from typing import ClassVar

from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from materials.models import Course, Lesson
from materials.validators import YoutubeUrlValidator
from users.models import Subscription


class LessonSerializer(ModelSerializer):
    class Meta:
        model = Lesson
        fields = "__all__"
        read_only_fields = ("owner",)
        validators = [YoutubeUrlValidator(field="video")]


class CourseSerializer(ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    count_lessons = serializers.SerializerMethodField()
    lessons = LessonSerializer(many=True, read_only=True)

    def get_count_lessons(self, obj):
        return obj.lessons.count()

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if not request or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(user=request.user, course=obj).exists()

    class Meta:
        model = Course
        fields: ClassVar[list[str]] = [
            "id",
            "name",
            "preview_image",
            "description",
            "count_lessons",
            "lessons",
            "is_subscribed",
        ]
