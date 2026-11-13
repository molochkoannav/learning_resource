from django.contrib.auth import get_user_model
from django.db.models.deletion import RestrictedError
from django.test import TestCase
from materials.models import Course, Lesson
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class CourseCRUDAPITests(APITestCase):
    """CRUD курсов через /materials/courses/ (CourseViewSet)."""

    @classmethod
    def setUpTestData(cls):
        cls.course_python = Course.objects.create(
            name="Python",
            description="Базовый курс по Python",
        )
        cls.course_django = Course.objects.create(
            name="Django",
            description="Разработка веб-приложений на Django",
        )

    def test_course_list_returns_all_courses(self):
        response = self.client.get("/materials/courses/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        names = {item["name"] for item in response.data}
        self.assertEqual(names, {"Python", "Django"})

    def test_course_create(self):
        payload = {"name": "REST API", "description": "Курс по DRF"}

        response = self.client.post("/materials/courses/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Course.objects.count(), 3)
        course = Course.objects.get(pk=response.data["id"])
        self.assertEqual(course.name, "REST API")
        self.assertEqual(course.description, "Курс по DRF")

    def test_course_create_requires_name_and_description(self):
        response = self.client.post("/materials/courses/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertIn("description", response.data)
        self.assertEqual(Course.objects.count(), 2)

    def test_course_retrieve(self):
        response = self.client.get(
            f"/materials/courses/{self.course_python.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.course_python.pk)
        self.assertEqual(response.data["name"], "Python")
        self.assertEqual(response.data["description"], "Базовый курс по Python")

    def test_course_update_put(self):
        payload = {"name": "Python Advanced", "description": "Углублённый Python"}

        response = self.client.put(
            f"/materials/courses/{self.course_python.pk}/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_python.refresh_from_db()
        self.assertEqual(self.course_python.name, "Python Advanced")
        self.assertEqual(self.course_python.description, "Углублённый Python")

    def test_course_partial_update_patch(self):
        response = self.client.patch(
            f"/materials/courses/{self.course_django.pk}/",
            {"description": "Новое описание"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_django.refresh_from_db()
        self.assertEqual(self.course_django.description, "Новое описание")
        self.assertEqual(self.course_django.name, "Django")

    def test_course_delete(self):
        response = self.client.delete(
            f"/materials/courses/{self.course_python.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(pk=self.course_python.pk).exists())
        self.assertEqual(Course.objects.count(), 1)

    def test_course_retrieve_unknown_returns_404(self):
        response = self.client.get("/materials/courses/999999/", format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LessonCRUDAPITests(APITestCase):
    """CRUD уроков через /materials/lessons/... ."""

    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            name="Python", description="Базовый курс по Python"
        )
        cls.other_course = Course.objects.create(
            name="Django", description="Курс по Django"
        )
        cls.lesson_intro = Lesson.objects.create(
            course=cls.course,
            name="Введение",
            description="Первый урок",
            video="https://example.com/intro",
        )
        cls.lesson_syntax = Lesson.objects.create(
            course=cls.course,
            name="Синтаксис",
            description="Основы синтаксиса",
        )
        cls.lesson_models = Lesson.objects.create(
            course=cls.other_course,
            name="Модели",
            description="Модели Django",
        )

    def test_lesson_list_returns_all_lessons(self):
        response = self.client.get("/materials/lessons/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        names = {item["name"] for item in response.data}
        self.assertEqual(names, {"Введение", "Синтаксис", "Модели"})

    def test_lesson_create(self):
        payload = {
            "course": self.course.pk,
            "name": "Функции",
            "description": "Определение и вызов функций",
            "video": "https://example.com/functions",
        }

        response = self.client.post(
            "/materials/lessons/create/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Lesson.objects.count(), 4)
        lesson = Lesson.objects.get(pk=response.data["id"])
        self.assertEqual(lesson.course_id, self.course.pk)
        self.assertEqual(lesson.name, "Функции")
        self.assertEqual(lesson.video, "https://example.com/functions")

    def test_lesson_create_without_course_fails(self):
        response = self.client.post(
            "/materials/lessons/create/",
            {"name": "Без курса"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("course", response.data)
        self.assertEqual(Lesson.objects.count(), 3)

    def test_lesson_create_with_unknown_course_fails(self):
        response = self.client.post(
            "/materials/lessons/create/",
            {"course": 999999, "name": "Без курса"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("course", response.data)
        self.assertEqual(Lesson.objects.count(), 3)

    def test_lesson_retrieve(self):
        response = self.client.get(
            f"/materials/lessons/{self.lesson_intro.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.lesson_intro.pk)
        self.assertEqual(response.data["name"], "Введение")
        self.assertEqual(response.data["course"], self.course.pk)

    def test_lesson_update_put(self):
        payload = {
            "course": self.other_course.pk,
            "name": "Введение (обновлено)",
            "description": "Обновлённое описание",
            "video": "https://example.com/updated",
        }

        response = self.client.put(
            f"/materials/lessons/{self.lesson_intro.pk}/update/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson_intro.refresh_from_db()
        self.assertEqual(self.lesson_intro.name, "Введение (обновлено)")
        self.assertEqual(self.lesson_intro.course_id, self.other_course.pk)
        self.assertEqual(self.lesson_intro.video, "https://example.com/updated")

    def test_lesson_partial_update_patch(self):
        response = self.client.patch(
            f"/materials/lessons/{self.lesson_syntax.pk}/update/",
            {"name": "Синтаксис (обновлено)"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson_syntax.refresh_from_db()
        self.assertEqual(self.lesson_syntax.name, "Синтаксис (обновлено)")
        self.assertEqual(self.lesson_syntax.course_id, self.course.pk)

    def test_lesson_delete(self):
        response = self.client.delete(
            f"/materials/lessons/{self.lesson_syntax.pk}/delete/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(pk=self.lesson_syntax.pk).exists())
        self.assertEqual(Lesson.objects.count(), 2)

    def test_lesson_retrieve_unknown_returns_404(self):
        response = self.client.get("/materials/lessons/999999/", format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CourseLessonRelationTests(TestCase):
    """Связь Course -> Lesson на уровне моделей."""

    def test_course_has_lessons_through_related_name(self):
        course = Course.objects.create(name="Python", description="Описание")
        Lesson.objects.create(course=course, name="Урок 1")
        Lesson.objects.create(course=course, name="Урок 2")

        self.assertEqual(course.lessons.count(), 2)

    def test_course_with_lessons_cannot_be_deleted(self):
        course = Course.objects.create(name="Python", description="Описание")
        Lesson.objects.create(course=course, name="Урок 1")

        with self.assertRaises(RestrictedError):
            course.delete()

        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        self.assertEqual(Lesson.objects.count(), 1)

    def test_lesson_can_be_deleted_and_course_stays(self):
        course = Course.objects.create(name="Python", description="Описание")
        lesson = Lesson.objects.create(course=course, name="Урок 1")

        lesson.delete()

        self.assertTrue(Course.objects.filter(pk=course.pk).exists())
        self.assertEqual(Lesson.objects.count(), 0)


class ProfileAPITests(APITestCase):
    """Профиль пользователя /users/profile/."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="alice@example.com",
            password="StrongPass123!",
            first_name="Alice",
            last_name="Smith",
            phone_number="+70000000001",
            city="Moscow",
        )
        cls.other_user = User.objects.create_user(
            email="bob@example.com",
            password="StrongPass123!",
            first_name="Bob",
            last_name="Brown",
            phone_number="+70000000002",
            city="Saint Petersburg",
        )

    def setUp(self):
        self.profile_url = "/users/profile/"

    def test_profile_requires_authentication(self):
        response = self.client.get(self.profile_url, format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_profile_update_requires_authentication(self):
        response = self.client.patch(
            self.profile_url,
            {"city": "Kazan"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, "Moscow")

    def test_authenticated_user_gets_own_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.profile_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.pk)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], "Alice")
        self.assertEqual(response.data["phone_number"], "+70000000001")
        self.assertEqual(response.data["city"], "Moscow")

    def test_profile_response_hides_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.profile_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data)

    def test_profile_patch_updates_own_data(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.profile_url,
            {"phone_number": "+79990000000", "city": "Kazan"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "+79990000000")
        self.assertEqual(self.user.city, "Kazan")
        self.assertEqual(self.user.email, "alice@example.com")

    def test_profile_put_updates_own_data(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            self.profile_url,
            {
                "email": "alice.new@example.com",
                "first_name": "Alice",
                "last_name": "Johnson",
                "phone_number": "+79991112233",
                "city": "Sochi",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice.new@example.com")
        self.assertEqual(self.user.last_name, "Johnson")
        self.assertEqual(self.user.phone_number, "+79991112233")
        self.assertEqual(self.user.city, "Sochi")

    def test_profile_update_does_not_change_other_users(self):
        self.client.force_authenticate(user=self.user)

        self.client.patch(
            self.profile_url,
            {"city": "Kazan"},
            format="json",
        )

        self.other_user.refresh_from_db()
        self.assertEqual(self.other_user.city, "Saint Petersburg")
        self.assertEqual(self.other_user.phone_number, "+70000000002")

    def test_profile_cannot_take_email_of_another_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.profile_url,
            {"email": self.other_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")
        self.assertEqual(self.other_user.email, "bob@example.com")


class CustomUserManagerTests(TestCase):
    """Кастомная модель/менеджер пользователя."""

    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(
            email="Test.User@EXAMPLE.COM",
            password="secret123",
        )

        self.assertEqual(user.email, "Test.User@example.com")
        self.assertTrue(user.check_password("secret123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="secret123")

    def test_create_superuser_sets_flags(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="secret123",
        )

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("secret123"))

    def test_str_returns_email(self):
        user = User.objects.create_user(
            email="str@example.com",
            password="secret123",
        )

        self.assertEqual(str(user), "str@example.com")
