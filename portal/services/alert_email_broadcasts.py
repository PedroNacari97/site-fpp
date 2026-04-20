from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape as html_escape
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils import timezone

from portal.models import (
    AlertEmailDigestItem,
    LeadAlertaEmail,
    OptInAlertaPassagem,
)
from portal.services.public_alerts import PUBLIC_HOME_ALERT_MAX_AGE_DAYS
from portal.templatetags.portal_extras import repair_portuguese_text


logger = logging.getLogger(__name__)

UNSUBSCRIBE_SCOPE = "alert-email-unsubscribe"
UNSUBSCRIBE_SALT = "portal.alerts.unsubscribe"


def _alerts_site_base_url() -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if base_url:
        return base_url
    return "http://localhost:8000"


def _absolute_alert_url(alerta_id: int) -> str:
    return f"{_alerts_site_base_url()}{reverse('portal_alerta_detalhe', args=[alerta_id])}"


def _absolute_alert_share_url(alerta_id: int) -> str:
    return f"{_alerts_site_base_url()}{reverse('portal_alerta_compartilhar', args=[alerta_id])}"


def _absolute_alerts_list_url() -> str:
    return f"{_alerts_site_base_url()}{reverse('portal_alertas')}"


def _absolute_unsubscribe_url(token: str) -> str:
    return f"{_alerts_site_base_url()}{reverse('portal_alertas_unsubscribe')}?token={token}"


def _format_date_list(raw_values) -> tuple[str, ...]:
    dates = []
    for raw_value in raw_values or []:
        try:
            parsed = date.fromisoformat(str(raw_value))
        except (TypeError, ValueError):
            continue
        label = parsed.strftime("%d/%m/%Y")
        if label not in dates:
            dates.append(label)
    return tuple(sorted(dates))


def _format_milhas(value) -> str:
    if value in (None, ""):
        return "Consulte o alerta no site"
    return f"{int(value):,}".replace(",", ".") + " milhas"


def _sanitize_whatsapp_number(raw_value: str) -> str:
    digits = re.sub(r"\D+", "", str(raw_value or ""))
    if not digits:
        return ""
    if digits.startswith("55"):
        return digits
    if len(digits) in {10, 11}:
        return f"55{digits}"
    return digits


def _build_whatsapp_digest_message() -> str:
    return "Olá! Recebi o e-mail de alertas da NC Fly e gostaria de falar sobre uma cotação."


def _whatsapp_contact_url(message: str | None = None) -> str:
    raw_number = (
        str(getattr(settings, "PORTAL_CONTACT_WHATSAPP", "") or "").strip()
        or str(getattr(settings, "PORTAL_CONTACT_PHONE", "") or "").strip()
    )
    number = _sanitize_whatsapp_number(raw_number)
    if not number:
        return ""
    if message:
        return f"https://wa.me/{number}?text={quote(message)}"
    return f"https://wa.me/{number}"


def capture_alert_email_snapshot(alerta) -> dict[str, object]:
    return {
        "publico": bool(alerta.deve_aparecer_na_vitrine(max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS)),
        "titulo": str(alerta.titulo or "").strip(),
        "origem": str(alerta.origem or "").strip().upper(),
        "destino": str(alerta.destino or "").strip().upper(),
        "cidade_destino": repair_portuguese_text(alerta.cidade_destino or ""),
        "programa": repair_portuguese_text(alerta.programa_fidelidade or ""),
        "companhia": repair_portuguese_text(alerta.companhia_aerea or ""),
        "classe": repair_portuguese_text(alerta.get_classe_display()),
        "valor_milhas": alerta.valor_milhas,
        "valor_reais": str(alerta.valor_reais or "").strip(),
        "datas_ida": _format_date_list(alerta.datas_ida),
        "datas_volta": _format_date_list(alerta.datas_volta),
    }


def _build_update_lines(previous_snapshot: dict[str, object], current_snapshot: dict[str, object]) -> list[str]:
    lines: list[str] = []

    previous_ida = set(previous_snapshot.get("datas_ida") or ())
    current_ida = tuple(current_snapshot.get("datas_ida") or ())
    new_ida = [item for item in current_ida if item not in previous_ida]
    if new_ida:
        lines.append("Novas datas de ida: " + ", ".join(new_ida))

    previous_volta = set(previous_snapshot.get("datas_volta") or ())
    current_volta = tuple(current_snapshot.get("datas_volta") or ())
    new_volta = [item for item in current_volta if item not in previous_volta]
    if new_volta:
        lines.append("Novas datas de volta: " + ", ".join(new_volta))

    if previous_snapshot.get("valor_milhas") != current_snapshot.get("valor_milhas"):
        lines.append("Milhas agora: " + _format_milhas(current_snapshot.get("valor_milhas")))

    if previous_snapshot.get("valor_reais") != current_snapshot.get("valor_reais") and current_snapshot.get("valor_reais"):
        lines.append(f"Valor em reais agora: R$ {current_snapshot['valor_reais']}")

    if previous_snapshot.get("companhia") != current_snapshot.get("companhia"):
        lines.append(f"Companhia atual: {current_snapshot['companhia']}")

    if previous_snapshot.get("programa") != current_snapshot.get("programa"):
        lines.append(f"Programa atual: {current_snapshot['programa']}")

    return lines


def _build_digest_metadata(alerta, *, kind: str, current_snapshot: dict[str, object], highlights: list[str] | None = None) -> dict[str, object]:
    route_label = f"{current_snapshot['origem']} para {current_snapshot['destino']}"
    return {
        "route_label": route_label,
        "destination_label": current_snapshot["cidade_destino"] or current_snapshot["destino"],
        "programa": current_snapshot["programa"],
        "companhia": current_snapshot["companhia"],
        "classe": current_snapshot["classe"],
        "milhas_label": _format_milhas(current_snapshot["valor_milhas"]),
        "highlights": list(highlights or []),
        "kind": kind,
    }


def notify_alert_subscribers(alerta, *, created: bool, previous_snapshot: dict[str, object] | None = None) -> bool:
    current_snapshot = capture_alert_email_snapshot(alerta)
    if not current_snapshot["publico"] or not current_snapshot.get("valor_milhas"):
        return False

    pending_item = (
        AlertEmailDigestItem.objects.filter(alerta=alerta, sent_at__isnull=True)
        .order_by("-created_at", "-id")
        .first()
    )

    if created or not previous_snapshot or not previous_snapshot.get("publico"):
        metadata = _build_digest_metadata(
            alerta,
            kind=AlertEmailDigestItem.KIND_NEW,
            current_snapshot=current_snapshot,
        )
        if pending_item:
            pending_item.kind = AlertEmailDigestItem.KIND_NEW
            pending_item.metadata_json = metadata
            pending_item.save(update_fields=["kind", "metadata_json"])
        else:
            AlertEmailDigestItem.objects.create(
                alerta=alerta,
                kind=AlertEmailDigestItem.KIND_NEW,
                metadata_json=metadata,
            )
        return True

    update_lines = _build_update_lines(previous_snapshot, current_snapshot)
    if not update_lines:
        return False

    if pending_item:
        if pending_item.kind == AlertEmailDigestItem.KIND_NEW:
            pending_item.metadata_json = _build_digest_metadata(
                alerta,
                kind=AlertEmailDigestItem.KIND_NEW,
                current_snapshot=current_snapshot,
            )
            pending_item.save(update_fields=["metadata_json"])
            return True

        existing_highlights = list((pending_item.metadata_json or {}).get("highlights") or [])
        for line in update_lines:
            if line not in existing_highlights:
                existing_highlights.append(line)
        pending_item.metadata_json = _build_digest_metadata(
            alerta,
            kind=AlertEmailDigestItem.KIND_UPDATED,
            current_snapshot=current_snapshot,
            highlights=existing_highlights,
        )
        pending_item.save(update_fields=["metadata_json"])
        return True

    AlertEmailDigestItem.objects.create(
        alerta=alerta,
        kind=AlertEmailDigestItem.KIND_UPDATED,
        metadata_json=_build_digest_metadata(
            alerta,
            kind=AlertEmailDigestItem.KIND_UPDATED,
            current_snapshot=current_snapshot,
            highlights=update_lines,
        ),
    )
    return True


def build_alert_unsubscribe_token(email: str) -> str:
    return signing.dumps(
        {"email": str(email or "").strip().lower(), "scope": UNSUBSCRIBE_SCOPE},
        salt=UNSUBSCRIBE_SALT,
    )


def get_email_from_unsubscribe_token(token: str) -> str | None:
    try:
        payload = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 365)
    except signing.BadSignature:
        return None

    if payload.get("scope") != UNSUBSCRIBE_SCOPE:
        return None

    email = str(payload.get("email") or "").strip().lower()
    return email or None


def get_alert_email_lead_by_unsubscribe_token(token: str) -> LeadAlertaEmail | None:
    email = get_email_from_unsubscribe_token(token)
    if not email:
        return None

    lead = LeadAlertaEmail.objects.filter(email=email).order_by("-id").first()
    if not lead:
        return None

    return lead


def has_active_alert_subscription_for_token(token: str) -> bool:
    """Indica se existe Lead ATIVO ou OptIn ATIVO para o email do token."""
    email = get_email_from_unsubscribe_token(token)
    if not email:
        return False
    has_lead = LeadAlertaEmail.objects.filter(
        email=email, status=LeadAlertaEmail.STATUS_ATIVO
    ).exists()
    has_optin = OptInAlertaPassagem.objects.filter(email=email, ativo=True).exists()
    return has_lead or has_optin


def unsubscribe_alert_email_by_token(token: str, *, motivo: str = "") -> LeadAlertaEmail | None:
    """Cancela a inscricao de alertas para o email do token.

    Cancela simultaneamente:
    - LeadAlertaEmail (captura de lead sem cadastro) se existir
    - OptInAlertaPassagem (PortalUser cadastrado no site) se existir

    Retorna o Lead quando encontrado (compat) ou None caso so exista opt-in.
    O canal OptInArtigoNovo (notificacao de novo modulo de estudo) NAO eh
    afetado — cancelamento eh granular por canal (LGPD).
    """
    email = get_email_from_unsubscribe_token(token)
    if not email:
        return None

    valid_motivos = {value for value, _label in LeadAlertaEmail.MOTIVO_CANCELAMENTO_CHOICES}
    motivo = str(motivo or "").strip()
    if motivo not in valid_motivos:
        motivo = ""

    lead = LeadAlertaEmail.objects.filter(email=email).order_by("-id").first()
    if lead and lead.status != LeadAlertaEmail.STATUS_DESCADASTRADO:
        update_fields = ["status", "cancelado_em", "atualizado_em"]
        lead.status = LeadAlertaEmail.STATUS_DESCADASTRADO
        lead.cancelado_em = timezone.now()
        if motivo:
            lead.motivo_cancelamento = motivo
            update_fields.append("motivo_cancelamento")
        lead.save(update_fields=update_fields)

    for opt in OptInAlertaPassagem.objects.filter(email=email, ativo=True):
        opt.cancelar(motivo=motivo or "unsubscribe_email")

    return lead


@dataclass(frozen=True)
class _AlertRecipient:
    """Adapter para unificar destinatarios de LeadAlertaEmail e PortalUser (opt-in)."""

    email: str
    first_name: str
    ref_id: str
    criado_em: datetime | None
    source: str  # "lead" ou "portal_user"


def _first_name_from_full_name(nome_completo: str, fallback: str = "cliente") -> str:
    nome = (nome_completo or "").strip()
    if not nome:
        return fallback
    return nome.split()[0]


def _recipient_from_lead(lead: LeadAlertaEmail) -> _AlertRecipient:
    return _AlertRecipient(
        email=lead.email,
        first_name=_first_name_from_full_name(lead.nome_completo or ""),
        ref_id=f"lead-{lead.id}",
        criado_em=getattr(lead, "criado_em", None),
        source="lead",
    )


def _recipient_from_optin(opt: OptInAlertaPassagem) -> _AlertRecipient:
    user = opt.user
    nome = getattr(user, "nome_completo", "") or ""
    return _AlertRecipient(
        email=opt.email or user.email,
        first_name=_first_name_from_full_name(nome),
        ref_id=f"pu-{user.id}",
        criado_em=getattr(opt, "criado_em", None),
        source="portal_user",
    )


def _build_digest_subject(items: list[AlertEmailDigestItem]) -> str:
    """Gera um assunto com os destinos do batch.

    Cada envio tem combinacao de destinos diferente, evitando que o Gmail
    agrupe todos os emails do dia no mesmo thread (usuario confundia qual
    informacao era a mais recente).
    """
    destinos: list[str] = []
    for item in items:
        metadata = item.metadata_json or {}
        label = (metadata.get("destination_label") or metadata.get("route_label") or "").strip()
        if not label:
            continue
        # Pega so o nome do destino (antes de virgula ou traco, se houver).
        short = label.split(",")[0].split(" - ")[0].strip()
        if short and short not in destinos:
            destinos.append(short)

    total = len(items)
    if not destinos:
        if total == 1:
            return "NC Fly Alertas: 1 atualização para conferir"
        return f"NC Fly Alertas: {total} atualizações para conferir"

    if len(destinos) == 1:
        return f"NC Fly Alertas: {destinos[0]}"
    if len(destinos) == 2:
        return f"NC Fly Alertas: {destinos[0]} e {destinos[1]}"

    primeiros = ", ".join(destinos[:2])
    restantes = len(destinos) - 2
    sufixo = "alerta" if restantes == 1 else "alertas"
    return f"NC Fly Alertas: {primeiros} e +{restantes} {sufixo}"


def _build_digest_body(recipient: _AlertRecipient, items: list[AlertEmailDigestItem], unsubscribe_url: str) -> str:
    lines = [
        f"Olá, {recipient.first_name}.",
        "",
        "Separamos os alertas e atualizações mais recentes da NC Fly para você conferir hoje.",
        "",
    ]

    for index, item in enumerate(items, start=1):
        metadata = item.metadata_json or {}
        route_label = metadata.get("route_label") or f"Alerta #{item.alerta_id}"
        alert_url = _absolute_alert_url(item.alerta_id)
        milhas_label = metadata.get("milhas_label") or "Consulte o alerta no site"
        share_url = _absolute_alert_share_url(item.alerta_id)
        if item.kind == AlertEmailDigestItem.KIND_NEW:
            lines.extend(
                [
                    f"{index}. Novo alerta: {route_label}",
                    f"Destino: {metadata.get('destination_label') or '-'}",
                    f"Programa: {metadata.get('programa') or '-'}",
                    f"Companhia: {metadata.get('companhia') or '-'}",
                    f"Classe: {metadata.get('classe') or '-'}",
                    f"Milhas: {milhas_label}",
                    f"Ver alerta: {alert_url}",
                    f"Compartilhar alerta: {share_url}",
                    "",
                ]
            )
            continue

        lines.append(f"{index}. Alerta atualizado: {route_label}")
        for highlight in metadata.get("highlights") or []:
            lines.append(f"- {highlight}")
        lines.append(f"Acompanhar alerta: {alert_url}")
        lines.append(f"Compartilhar alerta: {share_url}")
        lines.append("")

    whatsapp_url = _whatsapp_contact_url(_build_whatsapp_digest_message())
    if whatsapp_url:
        lines.extend(
            [
                "Precisa de ajuda com uma cotação ou quer falar com a equipe?",
                f"Fale com a NC Fly no WhatsApp: {whatsapp_url}",
                "",
            ]
        )

    lines.extend(
        [
            f"Ver todos os alertas: {_absolute_alerts_list_url()}",
            "",
            f"Cancelar inscricao: {unsubscribe_url}",
        ]
    )
    return "\n".join(lines)


def _build_digest_html_body(recipient: _AlertRecipient, items: list[AlertEmailDigestItem], unsubscribe_url: str) -> str:
    first_name = recipient.first_name
    item_blocks: list[str] = []

    for index, item in enumerate(items, start=1):
        metadata = item.metadata_json or {}
        route_label = metadata.get("route_label") or f"Alerta #{item.alerta_id}"
        alert_url = _absolute_alert_url(item.alerta_id)
        milhas_label = metadata.get("milhas_label") or "Consulte o alerta no site"
        share_url = _absolute_alert_share_url(item.alerta_id)

        if item.kind == AlertEmailDigestItem.KIND_NEW:
            item_blocks.append(
                f"""
                <div style="margin:0 0 16px;padding:18px 18px 16px;border:1px solid #f1d8ca;border-radius:18px;background:#fff8f3;">
                  <div style="margin:0 0 10px;font-size:14px;font-weight:700;color:#ff7a00;">{index}. Novo alerta</div>
                  <div style="margin:0 0 10px;font-size:20px;line-height:1.2;font-weight:800;color:#13294b;">{html_escape(str(route_label))}</div>
                  <div style="font-size:14px;line-height:1.7;color:#42526b;">
                    <div><strong>Destino:</strong> {html_escape(str(metadata.get('destination_label') or '-'))}</div>
                    <div><strong>Programa:</strong> {html_escape(str(metadata.get('programa') or '-'))}</div>
                    <div><strong>Companhia:</strong> {html_escape(str(metadata.get('companhia') or '-'))}</div>
                    <div><strong>Classe:</strong> {html_escape(str(metadata.get('classe') or '-'))}</div>
                    <div><strong>Milhas:</strong> {html_escape(str(milhas_label))}</div>
                  </div>
                  <div style="margin-top:14px;">
                    <a href="{html_escape(alert_url)}" style="display:block;padding:11px 16px;border-radius:999px;background:#13294b;color:#ffffff;text-align:center;text-decoration:none;font-size:14px;font-weight:700;">Ver alerta</a>
                    <a href="{html_escape(share_url)}" style="display:block;margin-top:8px;padding:10px 15px;border-radius:999px;border:1px solid #ff7a00;background:#ffffff;color:#ff7a00;text-align:center;text-decoration:none;font-size:14px;font-weight:800;">Compartilhar alerta</a>
                  </div>
                </div>
                """
            )
            continue

        highlights = "".join(
            f"<li style=\"margin:0 0 6px;\">{html_escape(str(highlight))}</li>"
            for highlight in (metadata.get("highlights") or [])
        )
        item_blocks.append(
            f"""
            <div style="margin:0 0 16px;padding:18px 18px 16px;border:1px solid #dbe5f4;border-radius:18px;background:#f8fbff;">
              <div style="margin:0 0 10px;font-size:14px;font-weight:700;color:#2f6fd6;">{index}. Alerta atualizado</div>
              <div style="margin:0 0 10px;font-size:20px;line-height:1.2;font-weight:800;color:#13294b;">{html_escape(str(route_label))}</div>
              <ul style="margin:0 0 14px 18px;padding:0;font-size:14px;line-height:1.7;color:#42526b;">
                {highlights}
              </ul>
              <a href="{html_escape(alert_url)}" style="display:block;padding:11px 16px;border-radius:999px;background:#13294b;color:#ffffff;text-align:center;text-decoration:none;font-size:14px;font-weight:700;">Acompanhar alerta</a>
              <a href="{html_escape(share_url)}" style="display:block;margin-top:8px;padding:10px 15px;border-radius:999px;border:1px solid #ff7a00;background:#ffffff;color:#ff7a00;text-align:center;text-decoration:none;font-size:14px;font-weight:800;">Compartilhar alerta</a>
            </div>
            """
        )

    whatsapp_url = _whatsapp_contact_url(_build_whatsapp_digest_message())
    whatsapp_block = ""
    if whatsapp_url:
        whatsapp_block = f"""
        <div style="margin:24px 0 0;padding:22px;border-radius:22px;background:#25d366;color:#111111;">
          <div style="margin:0 0 8px;font-size:18px;line-height:1.3;font-weight:800;">WhatsApp da NC Fly</div>
          <div style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#111111;">Se quiser falar com a equipe agora, use o atalho abaixo e abra a conversa com a mensagem pronta.</div>
          <a href="{html_escape(whatsapp_url)}" style="display:inline-block;padding:12px 18px;border-radius:999px;background:#ffffff;color:#128c4a;text-decoration:none;font-size:15px;font-weight:800;">
            &#128172; Falar no WhatsApp
          </a>
        </div>
        """

    alerts_url = _absolute_alerts_list_url()
    return f"""
    <html>
      <body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
        <div style="max-width:640px;margin:0 auto;padding:32px 28px;border-radius:28px;background:#ffffff;">
          <div style="margin:0 0 8px;font-size:12px;font-weight:800;letter-spacing:0.12em;color:#ff7a00;text-transform:uppercase;">NC Fly Alertas</div>
          <h1 style="margin:0 0 12px;font-size:30px;line-height:1.15;color:#13294b;">Olá, {html_escape(first_name)}.</h1>
          <p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#42526b;">Separamos os alertas e atualizações mais recentes da NC Fly para você conferir hoje.</p>
          {''.join(item_blocks)}
          {whatsapp_block}
          <div style="margin-top:24px;">
            <a href="{html_escape(alerts_url)}" style="display:inline-block;padding:12px 18px;border-radius:999px;background:#fff0e6;color:#ff7a00;text-decoration:none;font-size:14px;font-weight:800;">Ver todos os alertas</a>
          </div>
          <div style="margin-top:18px;padding-top:16px;border-top:1px solid #e2e8f0;">
            <div style="margin:0 0 8px;font-size:12px;line-height:1.6;color:#64748b;">Se quiser parar de receber estes alertas, voce pode cancelar sua inscricao em um clique.</div>
            <a href="{html_escape(unsubscribe_url)}" style="display:inline-block;padding:8px 14px;border-radius:999px;border:1px solid #cbd5e1;background:#f8fafc;color:#475569;text-decoration:none;font-size:12px;font-weight:700;">Cancelar inscricao</a>
          </div>
        </div>
      </body>
    </html>
    """


def _send_digest_to_recipient(recipient: _AlertRecipient, items: list[AlertEmailDigestItem]) -> bool:
    from_email = str(
        getattr(settings, "PORTAL_ALERTS_FROM_EMAIL", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    ).strip()
    if not from_email:
        return False

    reply_to = str(
        getattr(settings, "PORTAL_ALERTS_REPLY_TO", "")
        or getattr(settings, "PORTAL_CONTACT_EMAIL", "")
    ).strip()
    unsubscribe_token = build_alert_unsubscribe_token(recipient.email)
    unsubscribe_url = _absolute_unsubscribe_url(unsubscribe_token)
    mailto_unsubscribe = reply_to or from_email

    # X-Entity-Ref-ID unico por envio impede o Gmail de agrupar emails
    # consecutivos do dia na mesma thread.
    thread_ref = f"ncfly-alerts-{recipient.ref_id}-{int(timezone.now().timestamp() * 1000)}"
    headers = {
        "List-Unsubscribe": f"<mailto:{mailto_unsubscribe}?subject=Cancelar%20alertas>, <{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        "Precedence": "bulk",
        "X-Entity-Ref-ID": thread_ref,
    }

    message = EmailMultiAlternatives(
        subject=_build_digest_subject(items),
        body=_build_digest_body(recipient, items, unsubscribe_url),
        from_email=from_email,
        to=[recipient.email],
        reply_to=[reply_to] if reply_to else None,
        headers=headers,
    )
    message.attach_alternative(_build_digest_html_body(recipient, items, unsubscribe_url), "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Falha ao enviar digest de alertas para %s.", recipient.email)
        return False
    return True


def _resolve_target_slot_count(total_pending: int) -> int:
    if total_pending <= 0:
        return 0
    if total_pending <= 2:
        return 1
    if total_pending <= 6:
        return 2
    if total_pending <= 10:
        return 3
    return 4


# Teto absoluto por email: evita enviar dezenas de alertas em uma unica mensagem
# quando o volume do dia e alto. O que exceder esse cap fica na fila e sai nas
# proximas janelas (ou no dia seguinte).
DIGEST_HARD_CAP_PER_BATCH = 5


def _resolve_digest_batch_size(total_pending: int, *, max_items: int | None = None, remaining_slots: int | None = None) -> int:
    if total_pending <= 0:
        return 0

    if remaining_slots and int(remaining_slots) > 0:
        slot_count = min(
            max(1, int(remaining_slots)),
            _resolve_target_slot_count(total_pending),
        )
        computed = int(math.ceil(total_pending / slot_count))
        if max_items:
            computed = min(max(1, int(max_items)), computed)
        return max(1, min(computed, DIGEST_HARD_CAP_PER_BATCH))

    if max_items:
        return max(1, min(int(max_items), DIGEST_HARD_CAP_PER_BATCH))

    return min(total_pending, DIGEST_HARD_CAP_PER_BATCH)


def _eligible_digest_items_for_recipient(recipient: _AlertRecipient, items: list[AlertEmailDigestItem]) -> list[AlertEmailDigestItem]:
    if not recipient.criado_em:
        return list(items)
    return [item for item in items if item.created_at >= recipient.criado_em]


def _collect_alert_recipients() -> list[_AlertRecipient]:
    """Junta LeadAlertaEmail ativos + OptInAlertaPassagem ativos em um unico set.

    Dedup por email (lowercase). Quando o mesmo email estah nos dois lados,
    preferimos o Lead (historico mais antigo costuma estar aqui, e evita
    perder alertas anteriores ao cadastro do PortalUser).
    """
    seen: dict[str, _AlertRecipient] = {}

    for lead in LeadAlertaEmail.objects.filter(status=LeadAlertaEmail.STATUS_ATIVO).order_by("email"):
        key = (lead.email or "").strip().lower()
        if not key:
            continue
        seen.setdefault(key, _recipient_from_lead(lead))

    opt_qs = (
        OptInAlertaPassagem.objects.filter(ativo=True, user__ativo=True)
        .select_related("user")
        .order_by("email")
    )
    for opt in opt_qs:
        key = (opt.email or getattr(opt.user, "email", "") or "").strip().lower()
        if not key:
            continue
        seen.setdefault(key, _recipient_from_optin(opt))

    return list(seen.values())


def send_pending_alert_digest(*, max_items: int | None = None, remaining_slots: int | None = None) -> dict[str, int]:
    pending_qs = AlertEmailDigestItem.objects.filter(sent_at__isnull=True).order_by("created_at", "id")
    total_pending = pending_qs.count()
    batch_size = _resolve_digest_batch_size(
        total_pending,
        max_items=max_items,
        remaining_slots=remaining_slots,
    )
    items = list(pending_qs.select_related("alerta")[:batch_size]) if batch_size else []
    if not items:
        return {"items": 0, "recipients": 0, "emails_sent": 0}

    now = timezone.now()
    invalid_items = [item for item in items if not getattr(item.alerta, "valor_milhas", None)]
    if invalid_items:
        AlertEmailDigestItem.objects.filter(id__in=[item.id for item in invalid_items]).update(sent_at=now)
    items = [item for item in items if getattr(item.alerta, "valor_milhas", None)]
    if not items:
        return {"items": 0, "recipients": 0, "emails_sent": 0}

    recipients = _collect_alert_recipients()
    eligible_recipients = 0
    emails_sent = 0
    for recipient in recipients:
        eligible_items = _eligible_digest_items_for_recipient(recipient, items)
        if not eligible_items:
            continue
        eligible_recipients += 1
        if _send_digest_to_recipient(recipient, eligible_items):
            emails_sent += 1

    # Marcamos os itens como enviados sempre que a janela foi processada.
    # O comportamento antigo exigia sucesso em 100% dos destinatarios — em caso
    # de falha em qualquer lead, os mesmos itens voltavam na proxima janela
    # (ex.: 15h e 20h repetindo o conteudo das 12h), enquanto alertas novos
    # criados depois ficavam presos atras deles pela ordem por created_at.
    # A nova regra: se houve pelo menos um envio com sucesso, OU se nao havia
    # destinatarios elegiveis, marcamos o batch como consumido. Isso garante
    # avanco sequencial da fila e impede repeticao nas janelas seguintes.
    should_mark_sent = eligible_recipients == 0 or emails_sent > 0
    if should_mark_sent:
        AlertEmailDigestItem.objects.filter(id__in=[item.id for item in items]).update(sent_at=now)

    return {
        "items": len(items),
        "recipients": eligible_recipients,
        "emails_sent": emails_sent,
    }
