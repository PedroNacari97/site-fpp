"""Helpers para linkar PreUsers (visitantes anonimos) a PortalUsers.

Usado nas views de autenticacao (login por email, cadastro, Google OAuth)
para converter o rastreio anonimo em conversao atribuida.
"""
from __future__ import annotations

import logging

from django.utils import timezone


logger = logging.getLogger(__name__)


def link_pre_user_to(portal_user, request) -> None:
    """Liga o `PreUser` anonimo do request ao `PortalUser` autenticado.

    Chamado em `portal_login`, `portal_register` e `portal_google_callback`
    apos o login. Primeiro login -> grava `convertido_em`. Logins recorrentes
    sem PreUser novo nao alteram nada (o auto_now do `ultima_visita_em` ja foi
    atualizado pelo middleware).

    Degrada silencioso: qualquer exception nao impede a autenticacao.
    """
    try:
        pre_user = getattr(request, "pre_user", None)
        if pre_user is None or not getattr(portal_user, "pk", None):
            return
        # ja linkado? nao sobrescreve (preserva timestamp original de conversao)
        if pre_user.portal_user_id:
            return
        pre_user.portal_user = portal_user
        if not pre_user.convertido_em:
            pre_user.convertido_em = timezone.now()
        pre_user.save(update_fields=["portal_user", "convertido_em"])
    except Exception:
        logger.warning("link_pre_user_to falhou — seguindo sem linkar", exc_info=True)
