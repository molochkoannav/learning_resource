from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Course, Lessons

@shared_task
def send_course_update_notification(course_id):
    pass
#     """Отправляет уведомление об обновлении курса всем подписчикам."""
#     try:
#         course = Course.objects.get(id=course_id)
#         # Получаем email всех подписчиков этого курса
#         subscriber_emails = Subscription.objects.filter(
#             course=course
#         ).values_list('user__email', flat=True)

#         if subscriber_emails:
#             send_mail(
#                 subject=f'Обновление курса: {course.title}',
#                 message=f'Курс "{course.title}" был обновлен. Проверьте новые материалы!',
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 recipient_list=list(subscriber_emails),
#                 fail_silently=False,
#             )
#         return f'Уведомление отправлено {len(subscriber_emails)} подписчикам курса {course.title}'
#     except Exception as exc:
#         raise exc
