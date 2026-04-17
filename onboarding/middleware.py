import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

EXEMPT_PATHS = (
    "/contratar/",
    "/login/",
    "/ncadm/",
    "/django/admin/",
    "/accounts/",
    "/auth/",
    "/health/",
    "/home/",
    "/webhooks/",
    "/integracoes/",
    "/media/",
    "/static/",
    "/ads.txt",
    "/robots.txt",
    "/llms.txt",
    "/sitemap.xml",
    "/plataforma/",
    "/assinatura/bloqueada/",
)


class AssinaturaAtivaMiddleware:
    """
    Middleware que verifica se a empresa do usuario tem assinatura ativa.
    Bloqueia acesso ao painel B2B (/adm/ e /painel/) se nao tiver.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return self.get_response(request)

        path = request.path
        requires_check = path.startswith("/adm/") or path.startswith("/painel/")
        if not requires_check:
            return self.get_response(request)

        try:
            cliente = getattr(user, "cliente_gestao", None)
            if not cliente or not cliente.empresa_id:
                return self.get_response(request)

            assinatura = cliente.empresa.assinatura
        except Exception:
            return self.get_response(request)

        # Auto-expire trial
        if assinatura.status == "trial" and assinatura.trial_fim and assinatura.trial_fim <= timezone.now():
            assinatura.status = "inadimplente"
            assinatura.save(update_fields=["status"])

        if not assinatura.is_ativa:
            request.assinatura_ativa = False
            return redirect("assinatura_bloqueada")

        request.assinatura_ativa = True
        return self.get_response(request)

    def _is_exempt(self, request):
        path = request.path
        for exempt in EXEMPT_PATHS:
            if path.startswith(exempt):
                return True
        return False
