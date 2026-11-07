from django.urls import path

from rest_framework.routers import SimpleRouter
from materials.views import CourseViewSet, LessonCreateView, LessonListView, LessonRetrieveView, LessonUpdateView, LessonDestroyView
from materials.apps import MaterialsConfig


app_name = MaterialsConfig.name

router = SimpleRouter()
router.register("courses", CourseViewSet)

urlpatterns = [
    path("lessons/", LessonListView.as_view(), name="lessons_list"),
    path("lessons/<int:pk>/", LessonRetrieveView.as_view(), name="lesson_retrieve"),
    path("lessons/create/", LessonCreateView.as_view(), name="lesson_create"),
    path("lessons/<int:pk>/update/", LessonUpdateView.as_view(), name="lesson_update"),
    path("lessons/<int:pk>/delete/", LessonDestroyView.as_view(), name= "lesson_delete")
]

urlpatterns += router.urls
