"""Envio de notificacao de novo Artigo de Estudo para PortalUsers com OptInArtigoNovo.

Pipeline:
- ArtigoEstudo com status=published, notificado_em=NULL entra na fila.
- Para cada opt-in ativo (OptInArtigoNovo), envia 1 email (from=alerta@ncfly.com.br).
- Unsubscribe 1-clique usa o token_unsubscribe do proprio OptInArtigoNovo
  (canal granular: cancelar artigos nao cancela alertas de passagem, LGPD).
- Apos o batch, marca artigo.notificado_em = now().
"""
from __future__ import annotations

import logging
from html import escape as html_escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils import timezone

from portal.models import ArtigoEstudo, OptInArtigoNovo


logger = logging.getLogger(__name__)


def _site_base_url() -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if base_url:
        return base_url
    return "http://localhost:8000"


def _logo_url() -> str:
    logo_path = str(getattr(settings, "PORTAL_SITE_LOGO_URL", "") or "").strip()
    if not logo_path:
        return ""
    if logo_path.startswith("http://") or logo_path.startswith("https://"):
        return logo_path
    return f"{_site_base_url()}{logo_path}"


def _absolute_artigo_url(artigo: ArtigoEstudo) -> str:
    return f"{_site_base_url()}{artigo.get_absolute_url()}"


def _absolute_unsubscribe_url(opt: OptInArtigoNovo) -> str:
    return (
        f"{_site_base_url()}"
        f"{reverse('portal_optout_artigo', args=[opt.token_unsubscribe])}"
    )


def _first_name(opt: OptInArtigoNovo) -> str:
    nome = getattr(opt.user, "nome_completo", "") or ""
    nome = nome.strip()
    if not nome:
        return "viajante"
    return nome.split()[0]


def _build_subject(artigo: ArtigoEstudo) -> str:
    return f"NC Fly: novo artigo no ar, {artigo.titulo}"


def _build_text_body(artigo: ArtigoEstudo, opt: OptInArtigoNovo, unsubscribe_url: str) -> str:
    artigo_url = _absolute_artigo_url(artigo)
    modulo_titulo = getattr(getattr(artigo, "modulo", None), "titulo", "") or ""
    lines = [
        f"Olá, {_first_name(opt)}.",
        "",
        f"Publicamos um artigo novo no NC Fly: {artigo.titulo}.",
    ]
    if modulo_titulo:
        lines.append(f"Módulo: {modulo_titulo}.")
    resumo = (artigo.resumo or "").strip()
    if resumo:
        lines.extend(["", resumo])
    lines.extend(
        [
            "",
            f"Ler agora: {artigo_url}",
            "",
            f"Para cancelar somente os avisos de novos artigos: {unsubscribe_url}",
            "Os alertas de passagens seguem ativos, são canais separados.",
        ]
    )
    return "\n".join(lines)


def _build_html_body(artigo: ArtigoEstudo, opt: OptInArtigoNovo, unsubscribe_url: str) -> str:
    artigo_url = _absolute_artigo_url(artigo)
    logo_url = _logo_url()
    modulo_titulo = getattr(getattr(artigo, "modulo", None), "titulo", "") or ""
    resumo = (artigo.resumo or "").strip()

    logo_block = ""
    if logo_url:
        logo_block = (
            f'<div style="margin:0 0 18px;"><img src="{html_escape(logo_url)}" '
            f'alt="NC Fly" width="120" style="display:block;max-width:120px;height:auto;"></div>'
        )

    resumo_block = ""
    if resumo:
        resumo_block = (
            f'<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#42526b;">'
            f"{html_escape(resumo)}</p>"
        )

    modulo_line = ""
    if modulo_titulo:
        modulo_line = (
            f'<p style="margin:0 0 12px;font-size:13px;color:#64748b;">'
            f'Módulo: <strong style="color:#13294b;">{html_escape(modulo_titulo)}</strong></p>'
        )

    imagem_html = ""
    imagem = getattr(artigo, "imagem_exibicao", "") or ""
    if imagem and (imagem.startswith("http://") or imagem.startswith("https://")):
        imagem_html = (
            f'<img src="{html_escape(imagem)}" alt="{html_escape(artigo.titulo)}" '
            f'style="display:block;width:100%;max-width:100%;height:auto;border-radius:14px;margin:0 0 18px;">'
        )

    return f"""
    <html>
      <body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
        <div style="max-width:640px;margin:0 auto;padding:32px 28px;border-radius:28px;background:#ffffff;">
          {logo_block}
          <div style="margin:0 0 8px;font-size:12px;font-weight:800;letter-spacing:0.12em;color:#ff7a00;text-transform:uppercase;">Novo artigo no ar</div>
          <h1 style="margin:0 0 10px;font-size:26px;line-height:1.25;color:#13294b;">Olá, {html_escape(_first_name(opt))}.</h1>
          <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#13294b;">
            Publicamos um artigo novo pra você ler:
            <strong>{html_escape(artigo.titulo)}</strong>.
          </p>
          {modulo_line}
          {imagem_html}
          {resumo_block}
          <div style="margin-top:20px;">
            <a href="{html_escape(artigo_url)}" style="display:inline-block;padding:12px 18px;border-radius:999px;background:#13294b;color:#ffffff;text-decoration:none;font-size:14px;font-weight:800;">
              Ler artigo agora
            </a>
          </div>
          <div style="margin-top:22px;padding-top:16px;border-top:1px solid #e2e8f0;">
            <div style="margin:0 0 8px;font-size:12px;line-height:1.6;color:#64748b;">
              Se não quiser mais receber avisos de novos artigos, é só um clique. Seus alertas de passagens continuam ativos, são canais separados.
            </div>
            <a href="{html_escape(unsubscribe_url)}" style="display:inline-block;padding:8px 14px;border-radius:999px;border:1px solid #cbd5e1;background:#f8fafc;color:#475569;text-decoration:none;font-size:12px;font-weight:700;">Cancelar avisos de artigos</a>
          </div>
        </div>
      </body>
    </html>
    """


def _send_artigo_to_optin(artigo: ArtigoEstudo, opt: OptInArtigoNovo) -> bool:
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

    unsubscribe_url = _absolute_unsubscribe_url(opt)
    mailto_unsubscribe = reply_to or from_email
    thread_ref = f"ncfly-artigo-{artigo.id}-pu-{opt.user_id}-{int(timezone.now().timestamp() * 1000)}"
    headers = {
        "List-Unsubscribe": (
            f"<mailto:{mailto_unsubscribe}?subject=Cancelar%20artigos>, <{unsubscribe_url}>"
        ),
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        "Precedence": "bulk",
        "X-Entity-Ref-ID": thread_ref,
    }

    message = EmailMultiAlternatives(
        subject=_build_subject(artigo),
        body=_build_text_body(artigo, opt, unsubscribe_url),
        from_email=from_email,
        to=[opt.email],
        reply_to=[reply_to] if reply_to else None,
        headers=headers,
    )
    message.attach_alternative(_build_html_body(artigo, opt, unsubscribe_url), "text/html")
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Falha ao enviar notificacao de artigo novo %s para %s.", artigo.id, opt.email
        )
        return False
    return True


def send_artigo_notifications(artigo: ArtigoEstudo) -> dict[str, int]:
    """Envia notificacao de 1 artigo especifico para todos os opt-ins ativos."""
    destinatarios = 0
    enviados = 0
    opt_qs = (
        OptInArtigoNovo.objects.filter(ativo=True, user__ativo=True)
        .select_related("user")
        .order_by("email")
    )
    for opt in opt_qs:
        if not opt.email:
            continue
        destinatarios += 1
        if _send_artigo_to_optin(artigo, opt):
            enviados += 1

    if destinatarios == 0 or enviados > 0:
        artigo.notificado_em = timezone.now()
        artigo.save(update_fields=["notificado_em", "atualizado_em"])

    return {"destinatarios": destinatarios, "enviados": enviados}


def dispatch_pending_artigo_notifications() -> dict[str, int]:
    """Processa artigos publicados que ainda nao foram notificados."""
    pending = (
        ArtigoEstudo.objects.filter(status="published", notificado_em__isnull=True)
        .select_related("modulo")
        .order_by("publicado_em", "id")
    )
    total_artigos = 0
    total_destinatarios = 0
    total_enviados = 0
    for artigo in pending:
        total_artigos += 1
        result = send_artigo_notifications(artigo)
        total_destinatarios += result["destinatarios"]
        total_enviados += result["enviados"]
    return {
        "artigos": total_artigos,
        "destinatarios": total_destinatarios,
        "enviados": total_enviados,
    }
