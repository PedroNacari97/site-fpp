"""Views da área /adm/ para a barra de notificações.

Padronizadas por tipo, com ações individuais e em massa.
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from gestao.models import NotificacaoSistema
from gestao.services.dashboard import (
    build_operational_notifications,
    group_notifications_by_type,
    mark_all_operational_notifications_as_read,
    mark_operational_notification_as_read,
)

from .permissions import get_request_empresa, require_admin_or_operator


def _safe_redirect(request, fallback_name="admin_notificacoes"):
    redirect_url = request.POST.get("next") or request.GET.get("next")
    if redirect_url and redirect_url.startswith("/"):
        return redirect(redirect_url)
    return redirect(reverse(fallback_name))


@login_required
def admin_notificacoes(request):
    """Lista completa de notificações com filtros e ações em massa."""
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    empresa = get_request_empresa(request)

    # Notificações dinâmicas (não-lidas ainda ativas)
    dynamic_notifications = build_operational_notifications(
        user=request.user,
        empresa=empresa,
        limit=50,
    )
    grupos_dinamicos = group_notifications_by_type(dynamic_notifications)

    # Notificações persistidas (histórico: lidas não arquivadas)
    persistidas_qs = (
        NotificacaoSistema.objects.do_usuario(request.user)
        .ativas()
        .order_by("-criado_em")
    )
    if empresa is not None:
        persistidas_qs = persistidas_qs.da_empresa(empresa)

    filtro_tipo = request.GET.get("tipo") or ""
    if filtro_tipo:
        persistidas_qs = persistidas_qs.filter(tipo=filtro_tipo)

    filtro_estado = request.GET.get("estado") or "todas"
    if filtro_estado == "nao_lidas":
        persistidas_qs = persistidas_qs.filter(lida=False)
    elif filtro_estado == "lidas":
        persistidas_qs = persistidas_qs.filter(lida=True)

    historico = list(persistidas_qs[:200])

    context = {
        "menu_ativo": "notificacoes",
        "dynamic_notifications": dynamic_notifications,
        "grupos_dinamicos": grupos_dinamicos,
        "total_nao_lidas": len(dynamic_notifications),
        "historico": historico,
        "tipos_disponiveis": NotificacaoSistema.Tipo.choices,
        "filtro_tipo": filtro_tipo,
        "filtro_estado": filtro_estado,
    }
    return render(request, "admin_custom/notificacoes.html", context)


@login_required
@require_POST
def marcar_notificacao_lida_por_chave(request):
    """Endpoint já existente: mantém compat para JS do dropdown."""
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Payload invalido."}, status=400)

    notification_key = (payload.get("key") or "").strip()
    if not notification_key:
        return JsonResponse({"ok": False, "error": "Notificacao invalida."}, status=400)

    empresa = get_request_empresa(request)
    notifications = build_operational_notifications(
        user=request.user,
        empresa=empresa,
        limit=50,
    )
    notification = next(
        (item for item in notifications if item.get("key") == notification_key),
        None,
    )
    if notification is None:
        return JsonResponse({"ok": False, "error": "Notificacao nao encontrada."}, status=404)

    mark_operational_notification_as_read(
        user=request.user,
        key=notification_key,
        empresa=empresa,
        notification=notification,
    )

    unread_count = len(
        build_operational_notifications(
            user=request.user,
            empresa=empresa,
            limit=50,
        )
    )
    return JsonResponse({"ok": True, "unread_count": unread_count})


@login_required
@require_POST
def marcar_todas_lidas(request):
    """Marca todas notificações visíveis do usuário como lidas. Aceita JSON ou form."""
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    empresa = get_request_empresa(request)
    total = mark_all_operational_notifications_as_read(user=request.user, empresa=empresa)

    if request.headers.get("Accept") == "application/json" or request.content_type == "application/json":
        return JsonResponse({"ok": True, "marcadas": total, "unread_count": 0})
    return _safe_redirect(request)


@login_required
@require_POST
def marcar_notificacao_lida_por_id(request, notificacao_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    empresa = get_request_empresa(request)
    qs = NotificacaoSistema.objects.do_usuario(request.user)
    if empresa is not None:
        qs = qs.da_empresa(empresa)
    notificacao = get_object_or_404(qs, pk=notificacao_id)
    notificacao.marcar_lida()

    if request.content_type == "application/json":
        return JsonResponse({"ok": True, "id": notificacao.id})
    return _safe_redirect(request)


@login_required
@require_POST
def arquivar_notificacao(request, notificacao_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    empresa = get_request_empresa(request)
    qs = NotificacaoSistema.objects.do_usuario(request.user)
    if empresa is not None:
        qs = qs.da_empresa(empresa)
    notificacao = get_object_or_404(qs, pk=notificacao_id)
    notificacao.arquivar()

    if request.content_type == "application/json":
        return JsonResponse({"ok": True, "id": notificacao.id, "arquivada": True})
    return _safe_redirect(request)


@login_required
@require_POST
def arquivar_por_chave(request):
    """Arquiva notificação dinâmica — cria registro persistido já arquivado.

    Útil para o botão "x" no dropdown, quando a notificação ainda não existe no banco.
    """
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Payload invalido."}, status=400)

    notification_key = (payload.get("key") or "").strip()
    if not notification_key:
        return JsonResponse({"ok": False, "error": "Chave invalida."}, status=400)

    empresa = get_request_empresa(request)
    notifications = build_operational_notifications(
        user=request.user,
        empresa=empresa,
        limit=100,
    )
    notification = next(
        (item for item in notifications if item.get("key") == notification_key),
        None,
    )
    if notification is None:
        # Talvez já persistida — tenta localizar e arquivar
        existente = (
            NotificacaoSistema.objects.do_usuario(request.user)
            .filter(chave=notification_key)
            .first()
        )
        if existente is None:
            return JsonResponse({"ok": False, "error": "Notificacao nao encontrada."}, status=404)
        existente.arquivar()
        return JsonResponse({"ok": True, "arquivada": True})

    record = mark_operational_notification_as_read(
        user=request.user,
        key=notification_key,
        empresa=empresa,
        notification=notification,
    )
    if record is not None:
        record.arquivar()

    unread_count = len(
        build_operational_notifications(
            user=request.user,
            empresa=empresa,
            limit=50,
        )
    )
    return JsonResponse({"ok": True, "arquivada": True, "unread_count": unread_count})
