from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from gestao.models import Cliente
from gestao.utils import sync_cliente_activation


@receiver(user_logged_in)
def enforce_single_session(sender, request, user, **kwargs):
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id) and session.session_key != request.session.session_key:
            session.delete()


@receiver(post_save, sender=Cliente)
def sync_cliente_status(sender, instance, **kwargs):
    sync_cliente_activation(instance)
