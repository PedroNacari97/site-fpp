"""Cria NotificacaoSistema (alerta dentro do portal) quando o monitoramento
detecta uma mudanca relevante. Substitui o envio de email enquanto o canal
externo nao esta autorizado pelo cliente final.
"""
from __future__ import annotations

import logging

from django.urls import NoReverseMatch, reverse

from gestao.models import AcompanhamentoPassagem, NotificacaoSistema

from .comparator import MudancaDetectada

logger = logging.getLogger(__name__)


def _empresa_e_usuario(acompanhamento: AcompanhamentoPassagem):
    cliente = getattr(acompanhamento.emissao, "cliente", None)
    empresa = getattr(cliente, "empresa", None)
    usuario = getattr(cliente, "usuario", None)
    return empresa, usuario


def _url_acompanhamento(emissao_id: int) -> str:
    try:
        return reverse("admin_emissao_acompanhamento", args=[emissao_id])
    except NoReverseMatch:
        return ""


def criar_notificacao_mudanca(
    acompanhamento: AcompanhamentoPassagem,
    mudanca: MudancaDetectada,
) -> bool:
    """Cria/atualiza uma NotificacaoSistema sobre a mudanca detectada.

    Idempotente por (usuario, chave): se o mesmo (acompanhamento, status novo)
    ja gerou notificacao nao-arquivada, ela e reutilizada (e marcada como nao-lida)
    em vez de duplicar.
    """
    if not acompanhamento.notificar_passageiro:
        # Mesmo flag usado pelo email — operador pode silenciar uma reserva inteira.
        return False
    if not mudanca.relevante_para_passageiro:
        return False

    empresa, usuario = _empresa_e_usuario(acompanhamento)
    if usuario is None:
        logger.warning(
            "Acompanhamento %s sem usuario para receber alerta no portal",
            acompanhamento.id,
        )
        return False

    emissao = acompanhamento.emissao
    localizador = emissao.localizador or "sem localizador"
    cia = getattr(getattr(emissao, "companhia_aerea", None), "nome", "") or "companhia"
    chave = (
        f"alerta_passagem:{acompanhamento.id}"
        f":{mudanca.status_reserva_novo}:{mudanca.status_voo_novo}"
    )
    titulo = f"Status mudou: {localizador} ({cia})"
    mensagem = mudanca.resumo_humano().capitalize()
    url = _url_acompanhamento(emissao.id)

    notificacao, criada = NotificacaoSistema.objects.update_or_create(
        usuario=usuario,
        chave=chave,
        defaults={
            "empresa": empresa,
            "tipo": NotificacaoSistema.Tipo.ALERTA_PASSAGEM,
            "titulo": titulo[:255],
            "mensagem": mensagem,
            "url": url,
            "url_acao": url,
            "lida": False,
            "lida_em": None,
            "arquivada_em": None,
        },
    )
    logger.info(
        "Notificacao portal %s para acompanhamento %s (criada=%s)",
        notificacao.id,
        acompanhamento.id,
        criada,
    )
    return True
