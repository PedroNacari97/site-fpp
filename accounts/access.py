from django.conf import settings


def get_user_operational_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    return getattr(getattr(user, "cliente_gestao", None), "perfil", "")


def user_has_admin_panel_access(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or get_user_operational_role(user) in {"admin", "operador"}


def get_session_idle_timeout_seconds(user):
    if user_has_admin_panel_access(user):
        return settings.ADMIN_SESSION_IDLE_TIMEOUT_SECONDS
    return settings.USER_SESSION_IDLE_TIMEOUT_SECONDS
