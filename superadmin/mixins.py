"""
Mixin e decorator de controle de acesso para o painel superadmin NCfly.

Apenas o usuario cujo e-mail coincide com settings.SUPERADMIN_EMAIL tem acesso.
Qualquer tentativa de acesso por outro usuario resulta em HTTP 403.
"""
import functools
import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

logger = logging.getLogger(__name__)


def _is_superadmin(user) -> bool:
    """Retorna True se o usuario logado e o superadmin configurado."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    superadmin_email = getattr(settings, "SUPERADMIN_EMAIL", "pedro@ncfly.com.br")
    return (user.email or "").strip().lower() == superadmin_email.strip().lower()


class SuperAdminRequiredMixin(LoginRequiredMixin, View):
    """
    Mixin para Class-Based Views do painel superadmin.

    Uso:
        class MinhaView(SuperAdminRequiredMixin, TemplateView):
            ...
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse("superadmin_login"))

        if not _is_superadmin(request.user):
            logger.warning(
                "Acesso negado ao superadmin panel: user=%s ip=%s path=%s",
                getattr(request.user, "email", ""),
                request.META.get("REMOTE_ADDR", ""),
                request.path,
            )
            return HttpResponseForbidden(
                "<h1>403 — Acesso negado</h1>"
                "<p>Voce nao tem permissao para acessar esta area.</p>"
            )

        return super().dispatch(request, *args, **kwargs)


def superadmin_required(view_func):
    """
    Decorator para function-based views do painel superadmin.

    Uso:
        @superadmin_required
        def minha_view(request):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse("superadmin_login"))

        if not _is_superadmin(request.user):
            logger.warning(
                "Acesso negado ao superadmin panel: user=%s ip=%s path=%s",
                getattr(request.user, "email", ""),
                request.META.get("REMOTE_ADDR", ""),
                request.path,
            )
            return HttpResponseForbidden(
                "<h1>403 — Acesso negado</h1>"
                "<p>Voce nao tem permissao para acessar esta area.</p>"
            )

        return view_func(request, *args, **kwargs)

    return wrapper
