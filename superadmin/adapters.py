"""
Adapter do django-allauth que restringe o login via Google OAuth
exclusivamente ao e-mail configurado em settings.SUPERADMIN_EMAIL.

Qualquer tentativa de login social com outro e-mail e rejeitada com
ImmediateHttpResponse (redirect para /ncadm/ com mensagem de erro).
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)


class SuperadminOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Sobrescreve DefaultSocialAccountAdapter para garantir que apenas
    o e-mail definido em SUPERADMIN_EMAIL pode autenticar via Google OAuth.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Chamado apos o callback do Google, antes de criar/logar o usuario.
        Levanta ImmediateHttpResponse se o e-mail nao for o superadmin.
        """
        from allauth.exceptions import ImmediateHttpResponse

        email = ""
        if sociallogin.account.extra_data:
            email = (sociallogin.account.extra_data.get("email") or "").strip().lower()

        superadmin_email = getattr(settings, "SUPERADMIN_EMAIL", "pedro@ncfly.com.br").strip().lower()

        if email != superadmin_email:
            logger.warning(
                "Login Google rejeitado — e-mail nao autorizado: %s (ip=%s)",
                email,
                request.META.get("REMOTE_ADDR", ""),
            )
            messages.error(
                request,
                "Este e-mail nao tem permissao para acessar o painel.",
            )
            raise ImmediateHttpResponse(redirect(reverse("superadmin_login")))

    def is_auto_signup_allowed(self, request, sociallogin):
        """Desabilita criacao automatica de usuario via social login."""
        return False
