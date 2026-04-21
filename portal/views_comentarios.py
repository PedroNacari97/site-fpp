"""Views de comentarios do Portal B2C.

Endpoints:
- POST /home/artigos/<modulo>/<slug>/comentarios/          -> criar comentario/resposta
- POST /home/comentarios/<id>/editar/                      -> editar (autor, 15min)
- POST /home/comentarios/<id>/excluir/                     -> excluir (autor, 15min)
- GET  /home/artigos/<modulo>/<slug>/comentarios/lista/    -> paginacao AJAX
"""
from __future__ import annotations

import json

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from portal.auth import get_portal_user
from portal.models import ArtigoEstudo, ComentarioArtigo
from portal.services import comentarios as comentarios_service
from portal.services.comentarios import ComentarioError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_ajax(request) -> bool:
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("accept") or "")
    )


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _serializar_comentario(c: ComentarioArtigo, *, viewer_pk: int | None = None) -> dict:
    """Serializa pra front sem vazar dado pessoal."""
    pode_editar = (
        viewer_pk is not None
        and c.autor_id == viewer_pk
        and c.dentro_janela_edicao
        and c.is_publicado
    )
    return {
        "id": c.pk,
        "parent_id": c.parent_id,
        "corpo": c.corpo,
        "nome_exibicao": c.nome_exibicao,
        "inicial": c.inicial_avatar,
        "criado_em_iso": c.criado_em.isoformat() if c.criado_em else None,
        "editado": c.editado,
        "pode_editar": pode_editar,
        "pode_excluir": pode_editar,  # mesma janela
    }


def _require_login(request):
    user = get_portal_user(request)
    if not user:
        if _is_ajax(request):
            return None, JsonResponse({"error": "login_required"}, status=401)
        return None, redirect(f"{reverse('portal_login')}?next={request.get_full_path()}")
    return user, None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@require_http_methods(["POST"])
def criar(request, modulo_slug, slug):
    """Cria comentario ou resposta em um artigo."""
    user, err = _require_login(request)
    if err:
        return err

    artigo = get_object_or_404(
        ArtigoEstudo.objects.select_related("modulo"),
        slug=slug, modulo__slug=modulo_slug, status="published",
    )

    corpo = (request.POST.get("corpo") or "").strip()
    parent_id = request.POST.get("parent_id") or None
    try:
        parent_id = int(parent_id) if parent_id else None
    except (TypeError, ValueError):
        parent_id = None

    try:
        comentario = comentarios_service.criar_comentario(
            artigo=artigo,
            autor=user,
            corpo=corpo,
            parent_id=parent_id,
            ip=_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        )
    except ComentarioError as exc:
        if _is_ajax(request):
            return JsonResponse({"error": str(exc)}, status=400)
        return HttpResponseBadRequest(str(exc))
    except PermissionDenied:
        return JsonResponse({"error": "forbidden"}, status=403)

    if _is_ajax(request):
        return JsonResponse(
            {
                "ok": True,
                "comentario": _serializar_comentario(comentario, viewer_pk=user.pk),
            },
            status=201,
        )
    return redirect(f"{artigo.get_absolute_url()}#comentario-{comentario.pk}")


@require_http_methods(["POST"])
def editar(request, comentario_id):
    """Autor edita proprio comentario dentro da janela de 15min."""
    user, err = _require_login(request)
    if err:
        return err

    comentario = get_object_or_404(ComentarioArtigo, pk=comentario_id)
    novo_corpo = (request.POST.get("corpo") or "").strip()

    try:
        comentario = comentarios_service.editar_comentario(
            comentario=comentario, autor=user, novo_corpo=novo_corpo,
        )
    except PermissionDenied:
        return JsonResponse({"error": "forbidden"}, status=403)
    except ComentarioError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {"ok": True, "comentario": _serializar_comentario(comentario, viewer_pk=user.pk)}
    )


@require_http_methods(["POST"])
def excluir(request, comentario_id):
    """Autor exclui proprio comentario dentro da janela de 15min."""
    user, err = _require_login(request)
    if err:
        return err

    comentario = get_object_or_404(ComentarioArtigo, pk=comentario_id)

    try:
        comentarios_service.excluir_pelo_autor(comentario=comentario, autor=user)
    except PermissionDenied:
        return JsonResponse({"error": "forbidden"}, status=403)
    except ComentarioError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def listar(request, modulo_slug, slug):
    """Paginacao AJAX da lista de comentarios raiz (com respostas embutidas)."""
    artigo = get_object_or_404(
        ArtigoEstudo,
        slug=slug, modulo__slug=modulo_slug, status="published",
    )
    try:
        limit = max(1, min(int(request.GET.get("limit") or 10), 30))
        offset = max(0, int(request.GET.get("offset") or 0))
    except (TypeError, ValueError):
        limit, offset = 10, 0

    viewer = get_portal_user(request)
    viewer_pk = viewer.pk if viewer else None

    items, total = comentarios_service.listar_publicados_para_artigo(
        artigo, limit=limit, offset=offset,
    )

    data = []
    for c in items:
        serializado = _serializar_comentario(c, viewer_pk=viewer_pk)
        serializado["respostas"] = [
            _serializar_comentario(r, viewer_pk=viewer_pk)
            for r in c.respostas.all()
            if r.status == ComentarioArtigo.STATUS_PUBLICADO
        ]
        data.append(serializado)

    return JsonResponse({
        "items": data,
        "total": total,
        "offset": offset,
        "limit": limit,
        "tem_mais": offset + limit < total,
    })
