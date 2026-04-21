"""Servico de comentarios em ArtigoEstudo.

Regras:
- So PortalUser autenticado comenta
- Janela 15min pra autor editar/excluir (apos expira, so superadmin oculta)
- Rate limit: 5 comentarios/hora por autor
- Corpo sanitizado (escape de HTML — nao permite tags)
- Dispara notificacao por email pro admin (Pedro) em cada novo comentario
"""
from __future__ import annotations

import logging
from datetime import timedelta
from html import escape as html_escape

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from portal.models import (
    ArtigoEstudo,
    ComentarioArtigo,
    EDIT_JANELA_MINUTOS,
    PortalUser,
)


logger = logging.getLogger(__name__)


RATE_LIMIT_MAX_POR_HORA = 5
CORPO_MIN_CHARS = 2
CORPO_MAX_CHARS = 2000


class ComentarioError(Exception):
    """Erro de negocio ao manipular comentario."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitizar_corpo(corpo: str) -> str:
    """Normaliza + escapa HTML. Nao permite tags no comentario."""
    texto = (corpo or "").strip()
    # escape previne XSS direto no template via {{ corpo }}
    # templates usam |linebreaksbr para quebra de linha preservada
    texto = html_escape(texto, quote=False)
    return texto


def _validar_corpo(corpo: str) -> str:
    texto = _sanitizar_corpo(corpo)
    tamanho = len(texto)
    if tamanho < CORPO_MIN_CHARS:
        raise ComentarioError("Comentario muito curto.")
    if tamanho > CORPO_MAX_CHARS:
        raise ComentarioError(f"Comentario excede {CORPO_MAX_CHARS} caracteres.")
    return texto


def _validar_rate_limit(autor: PortalUser) -> None:
    uma_hora_atras = timezone.now() - timedelta(hours=1)
    recentes = ComentarioArtigo.objects.filter(
        autor=autor,
        criado_em__gte=uma_hora_atras,
    ).count()
    if recentes >= RATE_LIMIT_MAX_POR_HORA:
        raise ComentarioError(
            f"Limite de {RATE_LIMIT_MAX_POR_HORA} comentarios por hora atingido. "
            "Tente novamente mais tarde."
        )


def _resolver_parent(parent_id: int | None, artigo: ArtigoEstudo) -> ComentarioArtigo | None:
    """Resposta a resposta vira resposta ao raiz (1 nivel max)."""
    if not parent_id:
        return None
    try:
        parent = ComentarioArtigo.objects.select_related("parent").get(
            pk=parent_id,
            artigo=artigo,
            status=ComentarioArtigo.STATUS_PUBLICADO,
        )
    except ComentarioArtigo.DoesNotExist:
        raise ComentarioError("Comentario pai nao encontrado ou inativo.")
    # Se o parent ja e uma resposta, sobe para o raiz
    if parent.parent_id:
        return parent.parent
    return parent


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


@transaction.atomic
def criar_comentario(
    *,
    artigo: ArtigoEstudo,
    autor: PortalUser,
    corpo: str,
    parent_id: int | None = None,
    ip: str | None = None,
    user_agent: str = "",
    exibir_nome_completo: bool = False,
) -> ComentarioArtigo:
    """Cria comentario (ou resposta). Dispara notificacao admin em on_commit."""
    if not autor or not autor.ativo:
        raise PermissionDenied("Usuario nao autorizado.")

    texto = _validar_corpo(corpo)
    _validar_rate_limit(autor)

    parent = _resolver_parent(parent_id, artigo)

    comentario = ComentarioArtigo(
        artigo=artigo,
        autor=autor,
        parent=parent,
        corpo=texto,
        corpo_hash=ComentarioArtigo.calcular_hash(texto),
        exibir_nome_completo=exibir_nome_completo,
        ip_cadastro=ip or None,
        user_agent=(user_agent or "")[:2000],
    )
    comentario.aplicar_snapshot_autor()
    comentario.save()

    # Dispara email admin + email resposta (se aplicavel) apos commit bem-sucedido
    def _notificar():
        try:
            from portal.services.admin_notifications import (
                enviar_email_admin_novo_comentario,
                enviar_email_resposta_recebida,
            )
            enviar_email_admin_novo_comentario(comentario)
            if parent and parent.autor_id and parent.autor_id != autor.pk:
                enviar_email_resposta_recebida(comentario)
        except Exception:  # noqa: BLE001
            logger.exception("Falha disparando notificacoes de comentario %s", comentario.pk)

    transaction.on_commit(_notificar)

    return comentario


@transaction.atomic
def editar_comentario(
    *,
    comentario: ComentarioArtigo,
    autor: PortalUser,
    novo_corpo: str,
) -> ComentarioArtigo:
    """Autor edita proprio comentario dentro da janela de 15min."""
    if comentario.autor_id != getattr(autor, "pk", None):
        raise PermissionDenied("Apenas o autor pode editar.")
    if comentario.status != ComentarioArtigo.STATUS_PUBLICADO:
        raise ComentarioError("Comentario nao esta publicado.")
    if not comentario.dentro_janela_edicao:
        raise ComentarioError(
            f"Janela de edicao encerrada (apenas {EDIT_JANELA_MINUTOS}min apos publicacao)."
        )

    texto = _validar_corpo(novo_corpo)
    if texto == comentario.corpo:
        return comentario  # sem mudanca

    # grava versao anterior no historico pra auditoria
    historico = list(comentario.historico_edicoes or [])
    historico.append({
        "corpo": comentario.corpo,
        "corpo_hash": comentario.corpo_hash,
        "editado_em_iso": timezone.now().isoformat(),
    })
    comentario.historico_edicoes = historico

    comentario.corpo = texto
    comentario.corpo_hash = ComentarioArtigo.calcular_hash(texto)
    comentario.editado = True
    comentario.editado_em = timezone.now()
    comentario.save(update_fields=[
        "corpo", "corpo_hash", "editado", "editado_em",
        "historico_edicoes", "atualizado_em",
    ])
    return comentario


@transaction.atomic
def excluir_pelo_autor(
    *,
    comentario: ComentarioArtigo,
    autor: PortalUser,
) -> ComentarioArtigo:
    """Autor exclui proprio comentario dentro da janela de 15min."""
    if comentario.autor_id != getattr(autor, "pk", None):
        raise PermissionDenied("Apenas o autor pode excluir.")
    if comentario.status != ComentarioArtigo.STATUS_PUBLICADO:
        raise ComentarioError("Comentario nao esta publicado.")
    if not comentario.dentro_janela_edicao:
        raise ComentarioError(
            f"Janela de exclusao encerrada (apenas {EDIT_JANELA_MINUTOS}min apos publicacao)."
        )

    comentario.status = ComentarioArtigo.STATUS_EXCLUIDO_AUTOR
    comentario.excluido_em = timezone.now()
    comentario.save(update_fields=["status", "excluido_em", "atualizado_em"])
    return comentario


@transaction.atomic
def ocultar_pelo_admin(
    *,
    comentario: ComentarioArtigo,
    admin_user,
    motivo: str,
) -> ComentarioArtigo:
    """Superadmin oculta comentario (soft delete — mantem no banco)."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ComentarioError("Motivo obrigatorio ao ocultar.")
    if comentario.status == ComentarioArtigo.STATUS_OCULTO_ADMIN:
        return comentario  # idempotente

    comentario.status = ComentarioArtigo.STATUS_OCULTO_ADMIN
    comentario.ocultado_por = admin_user
    comentario.ocultado_em = timezone.now()
    comentario.motivo_ocultacao = motivo[:200]
    comentario.save(update_fields=[
        "status", "ocultado_por", "ocultado_em",
        "motivo_ocultacao", "atualizado_em",
    ])
    return comentario


@transaction.atomic
def restaurar_pelo_admin(
    *,
    comentario: ComentarioArtigo,
) -> ComentarioArtigo:
    """Reverte ocultacao (volta pra publicado). Nao restaura excluidos pelo autor."""
    if comentario.status != ComentarioArtigo.STATUS_OCULTO_ADMIN:
        raise ComentarioError("Somente comentarios ocultos podem ser restaurados.")
    comentario.status = ComentarioArtigo.STATUS_PUBLICADO
    comentario.ocultado_em = None
    comentario.motivo_ocultacao = ""
    # preserva ocultado_por pra trilha de auditoria historica
    comentario.save(update_fields=[
        "status", "ocultado_em", "motivo_ocultacao", "atualizado_em",
    ])
    return comentario


def listar_publicados_para_artigo(
    artigo: ArtigoEstudo,
    *,
    limit: int = 10,
    offset: int = 0,
):
    """Queryset paginado de comentarios raiz + respostas (no N+1)."""
    from django.db.models import Prefetch

    respostas_qs = (
        ComentarioArtigo.objects
        .filter(status=ComentarioArtigo.STATUS_PUBLICADO)
        .select_related("autor")
        .order_by("criado_em")
    )

    raiz = (
        ComentarioArtigo.objects
        .filter(
            artigo=artigo,
            parent__isnull=True,
            status=ComentarioArtigo.STATUS_PUBLICADO,
        )
        .select_related("autor")
        .prefetch_related(Prefetch("respostas", queryset=respostas_qs))
        .order_by("-criado_em")
    )

    total = raiz.count()
    items = list(raiz[offset:offset + limit])
    return items, total


def contar_publicados(artigo: ArtigoEstudo) -> int:
    """Conta total de comentarios publicados (raiz + respostas)."""
    return ComentarioArtigo.objects.filter(
        artigo=artigo,
        status=ComentarioArtigo.STATUS_PUBLICADO,
    ).count()


def anonimizar_comentarios_do_usuario(user: PortalUser) -> int:
    """LGPD art. 18 — titular solicita exclusao.

    Remove dados pessoais (email snapshot, nome, IP, UA, FK) mas mantem
    o corpo por interesse legitimo (coerencia de threads publicos).
    """
    count = 0
    for c in ComentarioArtigo.objects.filter(autor=user):
        c.autor = None
        c.autor_email_snapshot = ""
        c.autor_nome_snapshot = ""
        c.exibir_nome_completo = False
        c.ip_cadastro = None
        c.user_agent = ""
        c.save(update_fields=[
            "autor", "autor_email_snapshot", "autor_nome_snapshot",
            "exibir_nome_completo", "ip_cadastro", "user_agent",
            "atualizado_em",
        ])
        count += 1
    return count
