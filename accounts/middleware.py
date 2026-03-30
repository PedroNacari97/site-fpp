from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import render
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .access import get_session_idle_timeout_seconds, user_has_admin_panel_access
from .models import ActiveUserSession
from .security import log_security_event


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            active_session = ActiveUserSession.objects.filter(user=user).only(
                "session_key"
            ).first()
            current_session_key = request.session.session_key or ""
            if (
                active_session
                and active_session.session_key
                and active_session.session_key != current_session_key
            ):
                login_url = (
                    reverse("superadmin_login")
                    if user.is_superuser
                    else reverse("login_custom")
                )
                log_security_event(
                    "session_replaced",
                    request=request,
                    user=user,
                    details={"stored_session": active_session.session_key},
                )
                request._session_key_before_logout = current_session_key
                logout(request)
                messages.warning(
                    request,
                    "Sua conta foi acessada em outro dispositivo e esta sessao foi encerrada.",
                )
                return redirect(login_url)

        return self.get_response(request)


class SessionInactivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            timeout_seconds = get_session_idle_timeout_seconds(user)
            last_activity = request.session.get("last_activity_at")
            now_ts = int(timezone.now().timestamp())

            if last_activity and now_ts - int(last_activity) > timeout_seconds:
                login_url = (
                    reverse("superadmin_login")
                    if user.is_superuser
                    else reverse("login_custom")
                )
                log_security_event("session_timeout", request=request, user=user)
                request._session_key_before_logout = request.session.session_key or ""
                logout(request)
                messages.warning(
                    request,
                    "Sua sessao expirou por inatividade. Entre novamente para continuar.",
                )
                return redirect(login_url)

            request.session["last_activity_at"] = now_ts

        return self.get_response(request)


class AdminAreaAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/adm/")
            and getattr(request, "user", None)
            and request.user.is_authenticated
            and not user_has_admin_panel_access(request.user)
        ):
            log_security_event(
                "admin_area_denied",
                request=request,
                user=request.user,
                details={"path": request.path},
            )
            return render(request, "sem_permissao.html", status=403)

        return self.get_response(request)
