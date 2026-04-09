import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from portal.models import LeadAlertaEmail


logger = logging.getLogger(__name__)

ALERT_SOURCE_LABELS = {
    LeadAlertaEmail.ORIGEM_HOME: "Home publica",
    LeadAlertaEmail.ORIGEM_ALERTAS: "Pagina de alertas",
}


def _format_value(value, default="Nao informado"):
    normalized = str(value or "").strip()
    return normalized or default


def _format_datetime(value):
    if not value:
        return "Nao informado"
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def _send_lead_notification(subject, lines):
    recipients = [
        item.strip()
        for item in getattr(settings, "PORTAL_LEAD_NOTIFICATION_RECIPIENTS", [])
        if str(item).strip()
    ]
    if not recipients:
        return False

    try:
        send_mail(
            subject=subject,
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Falha ao enviar notificacao de lead por e-mail.")
        return False
    return True


def notify_alert_email_lead(lead, *, created):
    action_label = "Novo cadastro" if created else "Cadastro atualizado"
    source_label = ALERT_SOURCE_LABELS.get(lead.origem_cadastro, _format_value(lead.origem_cadastro))
    return _send_lead_notification(
        subject=f"[NC Fly] {action_label} de alertas por e-mail",
        lines=[
            f"{action_label} na lista de alertas por e-mail.",
            "",
            f"Nome: {_format_value(lead.nome_completo)}",
            f"E-mail: {_format_value(lead.email)}",
            f"Telefone: {_format_value(lead.telefone)}",
            f"Origem do cadastro: {source_label}",
            f"Status: {_format_value(lead.status)}",
            f"Versao do aceite: {_format_value(lead.aceite_versao)}",
            f"Aceito em: {_format_datetime(lead.aceito_em)}",
            f"IP: {_format_value(lead.aceito_ip)}",
            f"Ambiente: {_format_value(lead.source_environment)}",
            f"Host: {_format_value(lead.source_host)}",
        ],
    )


def notify_platform_lead(lead, *, capture_label):
    return _send_lead_notification(
        subject="[NC Fly] Novo lead da plataforma",
        lines=[
            "Novo lead da plataforma NC Fly.",
            "",
            f"Origem do formulario: {_format_value(capture_label)}",
            f"Nome: {_format_value(lead.nome_completo)}",
            f"Empresa: {_format_value(getattr(lead, 'empresa', ''))}",
            f"Cargo: {_format_value(getattr(lead, 'cargo', ''))}",
            f"E-mail: {_format_value(lead.email)}",
            f"Telefone: {_format_value(lead.telefone)}",
            f"Tamanho da equipe: {_format_value(getattr(lead, 'equipe_tamanho', ''))}",
            f"Mensagem: {_format_value(getattr(lead, 'mensagem', ''))}",
            f"Status: {_format_value(lead.status)}",
            f"Versao do aceite: {_format_value(lead.aceite_versao)}",
            f"Aceito em: {_format_datetime(lead.aceito_em)}",
            f"IP: {_format_value(lead.aceito_ip)}",
            f"Ambiente: {_format_value(lead.source_environment)}",
            f"Host: {_format_value(lead.source_host)}",
        ],
    )
