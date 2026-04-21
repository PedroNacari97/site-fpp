"""Notificacoes por email ao admin (Pedro) do NC Fly.

Eventos:
- Novo cadastro de PortalUser -> email com perfil do usuario
- Novo comentario publicado em ArtigoEstudo -> email com corpo e link
- Resposta recebida pelo autor do comentario pai

Envia assincrono via `transaction.on_commit` em quem chamar.
Se envio falhar, loga mas nao propaga excecao (degrada silencioso).
"""
from __future__ import annotations

import logging
from html import escape as html_escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse

from portal.models import ComentarioArtigo, PortalUser


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_email() -> str:
    return (
        str(getattr(settings, "ADMIN_COMMENT_EMAIL", "") or "").strip().lower()
        or str(getattr(settings, "SUPERADMIN_EMAIL", "") or "").strip().lower()
        or "pedro@ncfly.com.br"
    )


def _from_email() -> str:
    return (
        str(getattr(settings, "PORTAL_ALERTS_FROM_EMAIL", "") or "").strip()
        or str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
        or "no-reply@ncfly.com.br"
    )


def _site_base_url() -> str:
    base = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    return base or "http://localhost:8000"


def _absolute(path: str) -> str:
    if not path:
        return _site_base_url()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{_site_base_url()}{path}"


def _send(*, assunto: str, text: str, html: str, to: str) -> bool:
    try:
        msg = EmailMultiAlternatives(
            subject=assunto,
            body=text,
            from_email=_from_email(),
            to=[to],
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Falha enviando email admin para %s", to)
        return False


# ---------------------------------------------------------------------------
# 1. Novo cadastro de PortalUser
# ---------------------------------------------------------------------------


def enviar_email_admin_novo_cadastro(user: PortalUser, *, via: str = "email") -> bool:
    """Notifica o admin quando um novo PortalUser se cadastra."""
    admin = _admin_email()
    if not admin:
        return False

    nome = (user.nome or "").strip() or "(sem nome)"
    email = user.email
    ip = user.ip_cadastro or "-"
    ua = (user.user_agent_cadastro or "")[:200]
    criado = user.criado_em.strftime("%d/%m/%Y %H:%M") if user.criado_em else "-"
    admin_url = _absolute(reverse("superadmin_portal_usuarios")) if _tem_url("superadmin_portal_usuarios") else _site_base_url()

    assunto = f"[NCfly] Novo cadastro: {nome}"
    texto = (
        f"Novo usuario cadastrado no Portal B2C\n\n"
        f"Nome: {nome}\n"
        f"Email: {email}\n"
        f"Via: {via}\n"
        f"IP: {ip}\n"
        f"User-Agent: {ua}\n"
        f"Criado em: {criado}\n\n"
        f"Painel: {admin_url}\n"
    )

    html = f"""
    <html><body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,sans-serif;">
      <div style="max-width:560px;margin:0 auto;padding:28px;border-radius:20px;background:#fff;">
        <div style="margin:0 0 6px;font-size:12px;font-weight:800;letter-spacing:.1em;color:#0ea5e9;text-transform:uppercase;">Novo cadastro</div>
        <h1 style="margin:0 0 16px;font-size:22px;color:#13294b;">{html_escape(nome)}</h1>
        <table style="width:100%;border-collapse:collapse;font-size:14px;color:#334155;">
          <tr><td style="padding:6px 0;color:#64748b;width:120px;">Email</td><td style="padding:6px 0;"><strong>{html_escape(email)}</strong></td></tr>
          <tr><td style="padding:6px 0;color:#64748b;">Via</td><td style="padding:6px 0;">{html_escape(via)}</td></tr>
          <tr><td style="padding:6px 0;color:#64748b;">IP</td><td style="padding:6px 0;">{html_escape(ip)}</td></tr>
          <tr><td style="padding:6px 0;color:#64748b;">Criado</td><td style="padding:6px 0;">{html_escape(criado)}</td></tr>
        </table>
        <div style="margin-top:20px;">
          <a href="{html_escape(admin_url)}" style="display:inline-block;padding:10px 16px;border-radius:999px;background:#13294b;color:#fff;text-decoration:none;font-size:13px;font-weight:700;">Abrir painel</a>
        </div>
      </div>
    </body></html>
    """

    return _send(assunto=assunto, text=texto, html=html, to=admin)


# ---------------------------------------------------------------------------
# 2. Novo comentario publicado
# ---------------------------------------------------------------------------


def enviar_email_admin_novo_comentario(comentario: ComentarioArtigo) -> bool:
    """Notifica o admin quando alguem comenta em um artigo."""
    admin = _admin_email()
    if not admin:
        return False

    artigo = comentario.artigo
    autor_label = comentario.autor_nome_snapshot or comentario.autor_email_snapshot
    artigo_url = _absolute(artigo.get_absolute_url()) + f"#comentario-{comentario.pk}"
    ocultar_url = ""
    if _tem_url("superadmin_comentario_ocultar"):
        ocultar_url = _absolute(reverse("superadmin_comentario_ocultar", args=[comentario.pk]))

    corpo_resumo = comentario.corpo.strip()
    if len(corpo_resumo) > 600:
        corpo_resumo = corpo_resumo[:600] + "..."

    tipo = "Resposta" if comentario.parent_id else "Comentario"
    assunto = f"[NCfly] {tipo} em \"{artigo.titulo[:60]}\""

    texto_lines = [
        f"{tipo} novo em: {artigo.titulo}",
        "",
        f"Autor: {autor_label} ({comentario.autor_email_snapshot})",
        f"IP: {comentario.ip_cadastro or '-'}",
        "",
        "--- Comentario ---",
        corpo_resumo,
        "--- fim ---",
        "",
        f"Ver no site: {artigo_url}",
    ]
    if ocultar_url:
        texto_lines.append(f"Ocultar (admin): {ocultar_url}")

    texto = "\n".join(texto_lines)

    ocultar_btn = ""
    if ocultar_url:
        ocultar_btn = (
            f'<a href="{html_escape(ocultar_url)}" '
            f'style="display:inline-block;margin-left:8px;padding:10px 16px;border-radius:999px;'
            f'border:1px solid #cbd5e1;color:#475569;text-decoration:none;font-size:13px;font-weight:700;">Ocultar</a>'
        )

    html = f"""
    <html><body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,sans-serif;">
      <div style="max-width:640px;margin:0 auto;padding:28px;border-radius:20px;background:#fff;">
        <div style="margin:0 0 6px;font-size:12px;font-weight:800;letter-spacing:.1em;color:#f97316;text-transform:uppercase;">{html_escape(tipo)} novo</div>
        <h1 style="margin:0 0 16px;font-size:20px;color:#13294b;line-height:1.3;">{html_escape(artigo.titulo)}</h1>

        <div style="margin:0 0 14px;padding:14px 16px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;">
          <div style="margin:0 0 6px;font-size:13px;color:#64748b;">
            Por <strong style="color:#13294b;">{html_escape(autor_label)}</strong>
            &middot; {html_escape(comentario.autor_email_snapshot)}
          </div>
          <div style="margin:10px 0 0;font-size:15px;line-height:1.7;color:#13294b;white-space:pre-wrap;">{html_escape(corpo_resumo)}</div>
        </div>

        <div style="margin-top:18px;">
          <a href="{html_escape(artigo_url)}" style="display:inline-block;padding:10px 16px;border-radius:999px;background:#13294b;color:#fff;text-decoration:none;font-size:13px;font-weight:700;">Ver no site</a>
          {ocultar_btn}
        </div>
      </div>
    </body></html>
    """

    return _send(assunto=assunto, text=texto, html=html, to=admin)


# ---------------------------------------------------------------------------
# 3. Resposta recebida (avisa o autor do comentario pai)
# ---------------------------------------------------------------------------


def enviar_email_resposta_recebida(resposta: ComentarioArtigo) -> bool:
    """Avisa o autor do comentario raiz que ele recebeu uma resposta."""
    if not resposta.parent_id:
        return False
    parent = resposta.parent
    if not parent or not parent.autor_id:
        return False
    destinatario = parent.autor.email
    if not destinatario:
        return False

    artigo = resposta.artigo
    artigo_url = _absolute(artigo.get_absolute_url()) + f"#comentario-{resposta.pk}"
    autor_resposta = resposta.autor_nome_snapshot or resposta.autor_email_snapshot

    corpo_resumo = resposta.corpo.strip()
    if len(corpo_resumo) > 400:
        corpo_resumo = corpo_resumo[:400] + "..."

    assunto = f"[NCfly] {autor_resposta} respondeu seu comentario"

    texto = (
        f"Ola,\n\n"
        f"{autor_resposta} respondeu seu comentario no artigo \"{artigo.titulo}\":\n\n"
        f"--- Resposta ---\n{corpo_resumo}\n--- fim ---\n\n"
        f"Ver no site: {artigo_url}\n"
    )

    html = f"""
    <html><body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,sans-serif;">
      <div style="max-width:560px;margin:0 auto;padding:28px;border-radius:20px;background:#fff;">
        <div style="margin:0 0 6px;font-size:12px;font-weight:800;letter-spacing:.1em;color:#2563eb;text-transform:uppercase;">Nova resposta</div>
        <h1 style="margin:0 0 12px;font-size:20px;color:#13294b;line-height:1.3;">{html_escape(autor_resposta)} respondeu voce</h1>
        <p style="margin:0 0 14px;font-size:14px;color:#42526b;">No artigo <strong style="color:#13294b;">{html_escape(artigo.titulo)}</strong>:</p>

        <div style="padding:14px 16px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;">
          <div style="font-size:15px;line-height:1.7;color:#13294b;white-space:pre-wrap;">{html_escape(corpo_resumo)}</div>
        </div>

        <div style="margin-top:18px;">
          <a href="{html_escape(artigo_url)}" style="display:inline-block;padding:10px 16px;border-radius:999px;background:#13294b;color:#fff;text-decoration:none;font-size:13px;font-weight:700;">Responder no site</a>
        </div>
      </div>
    </body></html>
    """

    return _send(assunto=assunto, text=texto, html=html, to=destinatario)


# ---------------------------------------------------------------------------
# Utilitario
# ---------------------------------------------------------------------------


def _tem_url(nome: str) -> bool:
    try:
        reverse(nome)
        return True
    except Exception:  # noqa: BLE001
        try:
            reverse(nome, args=[1])
            return True
        except Exception:  # noqa: BLE001
            return False
