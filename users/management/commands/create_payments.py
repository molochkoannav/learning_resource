from django.core.management.base import BaseCommand
from users.models import Payment, CustomUser
from materials.models import Course, Lesson


class Command(BaseCommand):
    help =  help = (
        "Создание тестовых платежей. "
        "Штатный способ заполнения таблицы Payment тестовыми данными "
        "(см. README, раздел «Тестовые данные»)."
    )

    def handle(self, *args, **kwargs):
        user = CustomUser.objects.order_by("id").first()
        course = Course.objects.order_by("id").first()
        lesson = Lesson.objects.order_by("id").first()

        if not user:
            self.stdout.write(self.style.ERROR("Не найден пользователь"))
            return
        if not course or not lesson:
            self.stdout.write(self.style.ERROR("Не найдены курсы или уроки"))
            return

        Payment.objects.create(
            user=user, paid_course=course, amount=100, payment_method="card"
        )
        Payment.objects.create(
            user=user, paid_lesson=lesson, amount=200, payment_method="cash"
        )
        self.stdout.write(self.style.SUCCESS("Платежи созданы"))