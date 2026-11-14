from django.db import models
from django.conf import settings


class Course(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название")
    preview_image = models.ImageField(
        upload_to="courses/", null=True, blank=True, verbose_name="Превью изображение"
    )
    description = models.TextField(verbose_name="Описание")
    owner = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.PROTECT,
    related_name="courses",
    null=True,
    blank=True,
)
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"


class Lesson(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.RESTRICT, related_name="lessons", verbose_name="Курс"
    )
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(verbose_name="Описание", null=True, blank=True)
    preview_image = models.ImageField(
        upload_to="lessons/", null=True, blank=True, verbose_name="Превью изображение"
    )
    video = models.URLField(
        max_length=200, null=True, blank=True, verbose_name="Ссылка на видео"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lessons',
        null=True, blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
