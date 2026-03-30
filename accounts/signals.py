from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from gestao.models import Cliente
from gestao.utils import sync_cliente_activation

from .session_control import clear_active_session, ensure_session_key, register_active_session
from .security import log_security_event


@receiver(user_logged_in)
def enforce_single_session(sender, request, user, **kwargs):
    register_active_session(user, ensure_session_key(request))
    log_security_event("login_established", request=request, user=user)


@receiver(user_logged_out)
def clear_single_session(sender, request, user, **kwargs):
    if not request:
        return
    session_key = getattr(request, "_session_key_before_logout", None)
    if session_key:
        clear_active_session(user, session_key)
    log_security_event("logout", request=request, user=user)


@receiver(post_save, sender=Cliente)
def sync_cliente_status(sender, instance, **kwargs):
    sync_cliente_activation(instance)
