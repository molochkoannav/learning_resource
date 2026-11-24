from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.deletion import RestrictedError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from materials.models import Course, Lesson
from users.models import Subscription

User = get_user_model()

MODERATOR_GROUP_NAME = "Moderator"


class LessonCRUDAndPermissionTests(APITestCase):
    def setUp(self):
        self.moderator_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)

        self.owner = User.objects.create_user(
            email="owner@example.com", password="StrongPass123!"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="StrongPass123!"
        )
        self.moderator = User.objects.create_user(
            email="moderator@example.com", password="StrongPass123!"
        )
        self.moderator.groups.add(self.moderator_group)

        self.course = Course.objects.create(
            name="Python", description="Base course", owner=self.owner
        )
        self.other_course = Course.objects.create(
            name="Django", description="Other course", owner=self.other_user
        )

        self.lesson = Lesson.objects.create(
            course=self.course,
            name="Intro",
            description="Intro lesson",
            video="https://www.youtube.com/watch?v=intro",
            owner=self.owner,
        )
        self.other_lesson = Lesson.objects.create(
            course=self.other_course,
            name="Other intro",
            description="Other lesson",
            video="https://www.youtube.com/watch?v=other",
            owner=self.other_user,
        )

    def test_lesson_list_requires_authentication(self):
        response = self.client.get("/materials/lessons/", format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_owner_sees_only_own_lessons_in_list(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/materials/lessons/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.lesson.id)
        self.assertEqual(response.data[0]["name"], "Intro")

    def test_moderator_sees_all_lessons_in_list(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get("/materials/lessons/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        names = {item["name"] for item in response.data}
        self.assertEqual(names, {"Intro", "Other intro"})

    def test_owner_can_create_lesson(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "course": self.course.pk,
            "name": "Functions",
            "description": "Lesson about functions",
            "video": "https://www.youtube.com/watch?v=functions",
        }

        response = self.client.post("/materials/lessons/create/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Lesson.objects.count(), 3)
        lesson = Lesson.objects.get(pk=response.data["id"])
        self.assertEqual(lesson.name, "Functions")
        self.assertEqual(lesson.owner, self.owner)
        self.assertEqual(lesson.course_id, self.course.pk)

    def test_moderator_cannot_create_lesson(self):
        self.client.force_authenticate(user=self.moderator)
        payload = {
            "course": self.course.pk,
            "name": "Blocked",
            "description": "Should not be created",
            "video": "https://youtu.be/blocked",
        }

        response = self.client.post("/materials/lessons/create/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Lesson.objects.count(), 2)

    def test_lesson_create_rejects_non_youtube_video(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "course": self.course.pk,
            "name": "Bad video",
            "description": "Invalid link",
            "video": "https://example.com/video",
        }

        response = self.client.post("/materials/lessons/create/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Lesson.objects.count(), 2)

    def test_owner_can_retrieve_own_lesson(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(
            f"/materials/lessons/{self.lesson.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.lesson.pk)
        self.assertEqual(response.data["name"], "Intro")

    def test_moderator_can_retrieve_any_lesson(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get(
            f"/materials/lessons/{self.other_lesson.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.other_lesson.pk)

    def test_other_user_cannot_retrieve_foreign_lesson(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            f"/materials/lessons/{self.lesson.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_own_lesson(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "course": self.course.pk,
            "name": "Intro updated",
            "description": "Updated description",
            "video": "https://www.youtube.com/watch?v=updated",
        }

        response = self.client.put(
            f"/materials/lessons/{self.lesson.pk}/update/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, "Intro updated")
        self.assertEqual(self.lesson.description, "Updated description")
        self.assertEqual(self.lesson.video, "https://www.youtube.com/watch?v=updated")

    def test_owner_can_patch_own_lesson(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            f"/materials/lessons/{self.lesson.pk}/update/",
            {"name": "Intro patched"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, "Intro patched")
        self.assertEqual(self.lesson.course_id, self.course.pk)

    def test_moderator_can_update_lesson(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            f"/materials/lessons/{self.lesson.pk}/update/",
            {"name": "Moderated name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, "Moderated name")

    def test_other_user_cannot_update_foreign_lesson(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(
            f"/materials/lessons/{self.lesson.pk}/update/",
            {"name": "Hacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.name, "Intro")

    def test_owner_can_delete_own_lesson(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(
            f"/materials/lessons/{self.lesson.pk}/delete/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(pk=self.lesson.pk).exists())

    def test_moderator_cannot_delete_lesson(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(
            f"/materials/lessons/{self.lesson.pk}/delete/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Lesson.objects.filter(pk=self.lesson.pk).exists())

    def test_other_user_cannot_delete_foreign_lesson(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(
            f"/materials/lessons/{self.lesson.pk}/delete/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Lesson.objects.filter(pk=self.lesson.pk).exists())


class SubscriptionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sub@example.com", password="StrongPass123!"
        )
        self.other_user = User.objects.create_user(
            email="sub2@example.com", password="StrongPass123!"
        )
        self.course = Course.objects.create(
            name="Python", description="Course", owner=self.user
        )
        self.other_course = Course.objects.create(
            name="Django", description="Course 2", owner=self.other_user
        )
        self.subscribe_url = "/materials/subscribe/"

    def test_subscribe_requires_authentication(self):
        response = self.client.post(
            self.subscribe_url, {"course_id": self.course.pk}, format="json"
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(Subscription.objects.count(), 0)

    def test_subscribe_and_unsubscribe_toggle(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.subscribe_url, {"course_id": self.course.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "подписка добавлена")
        self.assertTrue(
            Subscription.objects.filter(user=self.user, course=self.course).exists()
        )

        response = self.client.post(
            self.subscribe_url, {"course_id": self.course.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "подписка удалена")
        self.assertFalse(
            Subscription.objects.filter(user=self.user, course=self.course).exists()
        )

    def test_subscribe_to_unknown_course_returns_404(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.subscribe_url, {"course_id": 999999}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_course_retrieve_shows_is_subscribed_for_current_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/materials/courses/{self.course.pk}/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_subscribed"])

        Subscription.objects.create(user=self.user, course=self.course)
        response = self.client.get(
            f"/materials/courses/{self.course.pk}/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_subscribed"])

    def test_subscription_is_user_specific(self):
        Subscription.objects.create(user=self.other_user, course=self.other_course)
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(
            f"/materials/courses/{self.other_course.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_subscribed"])

        self.client.force_authenticate(user=self.user)
        Subscription.objects.create(user=self.user, course=self.course)
        response = self.client.get(
            f"/materials/courses/{self.course.pk}/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_subscribed"])
        self.assertFalse(
            Subscription.objects.filter(
                user=self.user, course=self.other_course
            ).exists()
        )


class CourseCRUDAPITests(APITestCase):
    """CRUD по /materials/courses/ (CourseViewSet) с учетом прав доступа."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email="course_owner@example.com", password="StrongPass123!"
        )
        cls.other_user = User.objects.create_user(
            email="course_other@example.com", password="StrongPass123!"
        )
        cls.moderator = User.objects.create_user(
            email="course_moderator@example.com", password="StrongPass123!"
        )
        moderator_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
        cls.moderator.groups.add(moderator_group)

        cls.course_python = Course.objects.create(
            name="Python", description="Базовый курс по Python", owner=cls.owner
        )
        cls.course_django = Course.objects.create(
            name="Django", description="Фреймворк Django", owner=cls.other_user
        )

    def test_course_list_requires_authentication(self):
        response = self.client.get("/materials/courses/", format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_course_list_returns_only_own_courses_for_user(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/materials/courses/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Python")

    def test_course_list_returns_all_courses_for_moderator(self):
        self.client.force_authenticate(user=self.moderator)
        response = self.client.get("/materials/courses/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Python", "Django"})

    def test_course_create_by_authenticated_user(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"name": "REST API", "description": "Курс по DRF"}

        response = self.client.post("/materials/courses/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Course.objects.count(), 3)
        course = Course.objects.get(pk=response.data["id"])
        self.assertEqual(course.name, "REST API")
        self.assertEqual(course.owner, self.owner)

    def test_course_create_forbidden_for_moderator(self):
        self.client.force_authenticate(user=self.moderator)
        payload = {"name": "REST API", "description": "Курс по DRF"}

        response = self.client.post("/materials/courses/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_course_create_requires_name_and_description(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post("/materials/courses/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertIn("description", response.data)

    def test_course_retrieve_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            f"/materials/courses/{self.course_python.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.course_python.pk)
        self.assertEqual(response.data["name"], "Python")

    def test_course_retrieve_forbidden_for_non_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(
            f"/materials/courses/{self.course_django.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_course_update_put_by_owner(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"name": "Python Advanced", "description": "Продвинутый Python"}

        response = self.client.put(
            f"/materials/courses/{self.course_python.pk}/", payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_python.refresh_from_db()
        self.assertEqual(self.course_python.name, "Python Advanced")

    def test_course_partial_update_patch_by_moderator(self):
        self.client.force_authenticate(user=self.moderator)
        response = self.client.patch(
            f"/materials/courses/{self.course_django.pk}/",
            {"description": "Новое описание"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_django.refresh_from_db()
        self.assertEqual(self.course_django.description, "Новое описание")

    def test_course_delete_by_owner(self):
        self.client.force_authenticate(user=self.owner)
        deletable = Course.objects.create(
            name="Temp", description="Temp", owner=self.owner
        )
        response = self.client.delete(
            f"/materials/courses/{deletable.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(pk=deletable.pk).exists())

    def test_course_delete_forbidden_for_moderator(self):
        self.client.force_authenticate(user=self.moderator)
        response = self.client.delete(
            f"/materials/courses/{self.course_python.pk}/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Course.objects.filter(pk=self.course_python.pk).exists())


class CourseLessonRelationTests(TestCase):
    """Связь Course -> Lesson и правила удаления."""

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
        response = self.client.patch(self.profile_url, {"city": "Kazan"}, format="json")

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
        self.assertEqual(response.data["phone_number"], "+70000000001")
        self.assertEqual(response.data["city"], "Moscow")
        self.assertIn("payments", response.data)

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
                "phone_number": "+79991112233",
                "city": "Sochi",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice.new@example.com")
        self.assertEqual(self.user.phone_number, "+79991112233")
        self.assertEqual(self.user.city, "Sochi")

    def test_profile_update_does_not_change_other_users(self):
        self.client.force_authenticate(user=self.user)

        self.client.patch(self.profile_url, {"city": "Kazan"}, format="json")

        self.other_user.refresh_from_db()
        self.assertEqual(self.other_user.city, "Saint Petersburg")
        self.assertEqual(self.other_user.phone_number, "+70000000002")

    def test_profile_cannot_take_email_of_another_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.profile_url, {"email": self.other_user.email}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")
        self.assertEqual(self.other_user.email, "bob@example.com")


class CustomUserManagerTests(TestCase):
    """Тесты менеджера пользователей."""

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
