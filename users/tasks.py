from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

@shared_task
def deactivate_inactive_users():
    """Деактивирует пользователей, не заходивших более 30 дней."""
    inactive_period = timedelta(days=30)
    cutoff_date = timezone.now() - inactive_period
    inactive_users = User.objects.filter(
        last_login__lt=cutoff_date,
        is_active=True  
    )
    count = inactive_users.count()
    inactive_users.update(is_active=False)
    return f'Деактивировано {count} пользователей.'