from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from materials.models import Course, Lesson


class LessonSerializer(ModelSerializer):
    class Meta:
        model = Lesson
        fields = "__all__"

class CourseSerializer(ModelSerializer):
    count_lessons = serializers.SerializerMethodField()
    lessons = LessonSerializer(many=True, read_only=True)
    def get_count_lessons(self, obj):
        return obj.lesson.count()
    class Meta:
        model = Course
        fields = ["name", "preview_image", "description", "count_lessons", "lessons"]



