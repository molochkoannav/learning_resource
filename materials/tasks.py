from datetime import timedelta, timezone

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Course, Lessons
from users.models import Subscription


shared_task
def send_course_update_notification(course_id: int) -> str:
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return f'Курс с id={course_id} не найден.'

    now = timezone.now()
    cooldown = timedelta(hours=4)

    if course.last_notified_at and (now - course.last_notified_at) < cooldown:
        return f'Пропущено: прошло меньше 4 часов с последнего письма по "{course.title}".'

    subscriber_emails = list(
        Subscription.objects
        .filter(course=course)
        .values_list('user__email', flat=True)
        .exclude(user__email='')
    )

    if not subscriber_emails:
        return f'У курса "{course.title}" нет подписчиков.'

    send_mail(
        subject=f'Обновление курса: {course.title}',
        message=f'В курсе "{course.title}" появились новые материалы.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=subscriber_emails,
        fail_silently=False,
    )

    course.last_notified_at = now
    course.save(update_fields=['last_notified_at'])
    return f'Отправлено {len(subscriber_emails)} подписчикам курса "{course.title}".'