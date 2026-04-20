from __future__ import annotations

import logging
from email.utils import formataddr
from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import NoReverseMatch, reverse

from gestao.models import AcompanhamentoPassagem

from .comparator import MudancaDetectada

logger = logging.getLogger(__name__)


def _emails_destinatarios(acompanhamento: AcompanhamentoPassagem) -> list[str]:
    emails: list[str] = []
    if acompanhamento.email_consulta:
        emails.append(acompanhamento.email_consulta)
    primeiro_passageiro = acompanhamento.emissao.passageiros.order_by("id").first()
    if primeiro_passageiro and primeiro_passageiro.email:
        emails.append(primeiro_passageiro.email)
    cliente = getattr(acompanhamento.emissao, "cliente", None)
    cliente_user = getattr(cliente, "usuario", None)
    if cliente_user and cliente_user.email:
        emails.append(cliente_user.email)
    # Mantem ordem estavel removendo duplicatas
    visto: set[str] = set()
    finais: list[str] = []
    for email in emails:
        normalizado = email.strip().lower()
        if normalizado and normalizado not in visto:
            visto.add(normalizado)
            finais.append(email.strip())
    return finais


def _empresa_remetente(acompanhamento: AcompanhamentoPassagem):
    cliente = getattr(acompanhamento.emissao, "cliente", None)
    return getattr(cliente, "empresa", None)


def _from_address(empresa) -> str:
    nome_amigavel = (
        getattr(empresa, "nome", "")
        or getattr(empresa, "razao_social", "")
        or "Sua agência de viagens"
    )
    endereco = (
        getattr(settings, "MONITORAMENTO_ALERTAS_FROM_EMAIL", "")
        or getattr(settings, "PORTAL_ALERTS_FROM_EMAIL", "")
        or settings.DEFAULT_FROM_EMAIL
    )
    return formataddr((nome_amigavel, endereco))


def _reply_to(empresa) -> list[str]:
    email_contato = getattr(empresa, "email_contato", "") if empresa else ""
    return [email_contato] if email_contato else []


def _link_unsubscribe(acompanhamento: AcompanhamentoPassagem) -> str:
    base_url = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    try:
        path = reverse(
            "monitoramento_unsubscribe",
            kwargs={"token": str(acompanhamento.opt_out_token)},
        )
    except NoReverseMatch:
        return ""
    return f"{base_url}{path}" if base_url else path


def _texto_email(acompanhamento, mudanca, empresa, link_unsubscribe) -> str:
    emissao = acompanhamento.emissao
    nome_empresa = getattr(empresa, "nome", "") or "sua agência"
    contato = getattr(empresa, "email_contato", "") or ""
    trecho_origem = getattr(getattr(emissao, "aeroporto_partida", None), "sigla", "") or "---"
    trecho_destino = getattr(getattr(emissao, "aeroporto_destino", None), "sigla", "") or "---"
    data_ida = emissao.data_ida.strftime("%d/%m/%Y %H:%M") if emissao.data_ida else "data não informada"
    cia = getattr(getattr(emissao, "companhia_aerea", None), "nome", "") or "companhia aérea"

    linhas = [
        f"Olá!",
        "",
        f"A {nome_empresa} detectou uma atualização na sua reserva {emissao.localizador or ''} ({cia}).",
        f"Trecho: {trecho_origem} → {trecho_destino} em {data_ida}.",
        "",
        f"O que mudou: {mudanca.resumo_humano()}.",
        "",
        "Recomendamos confirmar diretamente no site da companhia aérea antes do embarque.",
    ]
    if contato:
        linhas.append("")
        linhas.append(f"Em caso de dúvida, responda este email ou fale com {nome_empresa} pelo {contato}.")
    if link_unsubscribe:
        linhas.append("")
        linhas.append(
            "Para parar de receber esses avisos sobre essa reserva, acesse: " + link_unsubscribe
        )
    linhas.append("")
    linhas.append(
        "Esse aviso foi enviado pela "
        f"{nome_empresa} usando a plataforma NCfly como operadora técnica."
    )
    return "\n".join(linhas)


def _html_email(texto: str) -> str:
    paragrafos = "".join(
        f"<p>{linha}</p>" for linha in texto.split("\n") if linha.strip()
    )
    return f"<div style=\"font-family: Arial, sans-serif; line-height: 1.5;\">{paragrafos}</div>"


def enviar_alerta_mudanca(
    acompanhamento: AcompanhamentoPassagem,
    mudanca: MudancaDetectada,
    *,
    destinatarios_extras: Iterable[str] = (),
) -> bool:
    """Envia email em nome da agência avisando o passageiro sobre mudança de status.

    Retorna ``True`` se algum email foi enviado (ou enfileirado pelo backend).
    Não levanta exceção em caso de falha — apenas loga, para não derrubar o fluxo
    de sincronização do operador.
    """

    if not acompanhamento.notificar_passageiro:
        logger.info("Acompanhamento %s com notificação desativada — email ignorado", acompanhamento.id)
        return False
    if not mudanca.relevante_para_passageiro:
        return False

    destinatarios = _emails_destinatarios(acompanhamento)
    destinatarios.extend(email for email in destinatarios_extras if email)
    if not destinatarios:
        logger.warning(
            "Acompanhamento %s sem destinatário válido — email não enviado", acompanhamento.id
        )
        return False

    empresa = _empresa_remetente(acompanhamento)
    from_address = _from_address(empresa)
    reply_to = _reply_to(empresa)
    link_unsubscribe = _link_unsubscribe(acompanhamento)

    assunto = (
        f"[{getattr(empresa, 'nome', 'Atualização de viagem')}] "
        f"Mudança no status da sua passagem {acompanhamento.emissao.localizador or ''}"
    ).strip()
    texto = _texto_email(acompanhamento, mudanca, empresa, link_unsubscribe)
    html = _html_email(texto)

    headers: dict[str, str] = {}
    if link_unsubscribe:
        headers["List-Unsubscribe"] = f"<{link_unsubscribe}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    mensagem = EmailMultiAlternatives(
        subject=assunto[:200],
        body=texto,
        from_email=from_address,
        to=destinatarios,
        reply_to=reply_to or None,
        headers=headers or None,
    )
    mensagem.attach_alternative(html, "text/html")

    try:
        enviados = mensagem.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Falha ao enviar email de alerta para acompanhamento %s", acompanhamento.id
        )
        return False
    return bool(enviados)
