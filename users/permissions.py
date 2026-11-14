from rest_framework.permissions import BasePermission, SAFE_METHODS

MODERATOR_GROUP_NAME = "Moderator"
class IsModerator(BasePermission):
        """Разрешает доступ только пользователям из группы moderators."""

        def has_permission(self, request, view):
            return (
                request.user.is_authenticated
                and request.user.groups.filter(name=MODERATOR_GROUP_NAME).exists()
            )

        def has_object_permission(self, request, view, obj):
            return self.has_permission(request, view)

class IsModeratorOrReadOnly(BasePermission):
    """
    Модератор может всё что угодно (кроме create/destroy — это контролируется в контроллере),
    остальные — только читать.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated
            and request.user.groups.filter(name=MODERATOR_GROUP_NAME).exists()
        )

class IsOwner(BasePermission):
    """
    Разрешает доступ только владельцу объекта.
    Для list (где объекта ещё нет) — возвращает True на уровне has_permission,
    а фильтрацию делает get_queryset() во вью.
    """
    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id