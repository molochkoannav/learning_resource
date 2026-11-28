from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from materials.models import Course
from users.models import Subscription


@shared_task
def send_course_update_notification(course_id: int) -> str:
    try:
        course = Course.objects.get(pk=course_id)
    except Course.DoesNotExist:
        return f"Курс с id={course_id} не найден."

    now = timezone.now()
    cooldown = timedelta(hours=4)

    if course.last_notified_at and now - course.last_notified_at < cooldown:
        return f'Уведомление по курсу «{course.name}» пока не отправляется.'

    emails = list(
        Subscription.objects.filter(course=course)
        .exclude(user__email="")
        .values_list("user__email", flat=True)
    )
    if not emails:
        return f'У курса «{course.name}» нет подписчиков.'

    send_mail(
        subject=f"Обновление курса: {course.name}",
        message=f"В курсе «{course.name}» появились новые материалы.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=emails,
        fail_silently=False,
    )
    course.last_notified_at = now
    course.save(update_fields=["last_notified_at"])
    return f"Отправлено {len(emails)} подписчикам."