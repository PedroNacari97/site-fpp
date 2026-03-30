from django.contrib.sessions.models import Session
from django.db import transaction

from .models import ActiveUserSession


def ensure_session_key(request):
    session_key = request.session.session_key
    if session_key:
        return session_key
    request.session.save()
    return request.session.session_key


def register_active_session(user, session_key):
    if not user or not session_key:
        return

    with transaction.atomic():
        active_session, _ = ActiveUserSession.objects.select_for_update().get_or_create(
            user=user
        )
        previous_session_key = active_session.session_key
        if previous_session_key and previous_session_key != session_key:
            Session.objects.filter(session_key=previous_session_key).delete()
        if previous_session_key != session_key:
            active_session.session_key = session_key
            active_session.save(update_fields=["session_key", "updated_at"])


def clear_active_session(user, session_key=None):
    if not user:
        return

    sessions = ActiveUserSession.objects.filter(user=user)
    if session_key:
        sessions = sessions.filter(session_key=session_key)
    sessions.update(session_key="")
