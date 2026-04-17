import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from gestao.models import EmissaoHotel, StageTransition
from gestao.models.stage_transition import HOTEL_STAGES, HOTEL_TRANSICOES
from .permissions import require_admin_or_operator, scope_queryset_to_company, ensure_company_access


_HOTEL_STAGE_SLUGS = {s[0] for s in HOTEL_STAGES}
_HOTEL_STAGE_LABELS = {s[0]: s[1] for s in HOTEL_STAGES}


def _avatar_info(user):
    if not user:
        return {"iniciais": "\u2014", "cor": "#94a3b8"}
    nome = user.first_name or user.last_name or user.username
    p = nome.strip()
    if not p:
        return {"iniciais": "?", "cor": "#94a3b8"}
    partes = p.split(" ")
    iniciais = "".join(p[0] for p in partes if p)[:2].upper()
    base = abs(hash(nome)) % 360
    cor = f"hsl({base}, 55%, 55%)"
    return {"iniciais": iniciais, "cor": cor}


def _hotel_card(obj):
    cliente = getattr(obj, "cliente", None)
    operador_user = getattr(obj, "criado_por", None)
    voo = getattr(obj, "voo_vinculado", None)
    voo_label = ""
    if voo:
        origem = getattr(voo.origem, "iata", "") if voo.origem else ""
        destino = getattr(voo.destino, "iata", "") if voo.destino else ""
        voo_label = f"{origem} \u2192 {destino}" if origem or destino else ""
    return {
        "tipo": "hotel",
        "id": obj.id,
        "cliente_nome": str(cliente) if cliente else "Sem cliente",
        "nome_hotel": obj.nome_hotel,
        "check_in": obj.check_in,
        "check_out": obj.check_out,
        "valor_pago": obj.valor_pago or 0,
        "economia": obj.economia_obtida or 0,
        "voo_label": voo_label,
        "avatar": _avatar_info(operador_user),
        "url_detalhe": reverse("admin_editar_emissao_hotel", args=(obj.id,)),
    }


def _has_url(name):
    try:
        reverse(name, args=(1,))
        return True
    except Exception:
        return False


@login_required
def pipeline_hotel_view(request):
    bloqueio = require_admin_or_operator(request)
    if bloqueio:
        return bloqueio

    base = EmissaoHotel.objects.select_related(
        "cliente__usuario", "cliente__criado_por", "cliente__empresa",
        "criado_por", "voo_vinculado__origem", "voo_vinculado__destino",
    )
    base = scope_queryset_to_company(base, request, "cliente__empresa")

    solicitado = [_hotel_card(h) for h in base.filter(status="solicitado").order_by("-criado_em")[:100]]
    cotado = [_hotel_card(h) for h in base.filter(status="cotado").order_by("-criado_em")[:100]]
    confirmado = [_hotel_card(h) for h in base.filter(status="confirmado").order_by("-check_in")[:100]]
    checkin = [_hotel_card(h) for h in base.filter(status="checkin").order_by("-check_in")[:100]]
    finalizado = [_hotel_card(h) for h in base.filter(status="finalizado").order_by("-check_out")[:100]]
    cancelado = [_hotel_card(h) for h in base.filter(status="cancelado").order_by("-criado_em")[:100]]

    def _destinos_com_nome(stage_id):
        slugs = sorted(HOTEL_TRANSICOES.get(stage_id, set()))
        return [{"slug": s, "nome": _HOTEL_STAGE_LABELS.get(s, s)} for s in slugs]

    def _destinos_json(stage_id):
        return mark_safe(json.dumps(sorted(HOTEL_TRANSICOES.get(stage_id, set()))))

    colunas = [
        {"id": "solicitado", "nome": "Solicitado", "acento": "primary", "cards": solicitado, "destinos": _destinos_com_nome("solicitado"), "destinos_json": _destinos_json("solicitado")},
        {"id": "cotado", "nome": "Cotado", "acento": "info", "cards": cotado, "destinos": _destinos_com_nome("cotado"), "destinos_json": _destinos_json("cotado")},
        {"id": "confirmado", "nome": "Confirmado", "acento": "success", "cards": confirmado, "destinos": _destinos_com_nome("confirmado"), "destinos_json": _destinos_json("confirmado")},
        {"id": "checkin", "nome": "Check-in", "acento": "warning", "cards": checkin, "destinos": _destinos_com_nome("checkin"), "destinos_json": _destinos_json("checkin")},
        {"id": "finalizado", "nome": "Finalizado", "acento": "muted", "cards": finalizado, "destinos": _destinos_com_nome("finalizado"), "destinos_json": _destinos_json("finalizado")},
        {"id": "cancelado", "nome": "Cancelado", "acento": "danger", "cards": cancelado, "destinos": _destinos_com_nome("cancelado"), "destinos_json": _destinos_json("cancelado")},
    ]

    context = {
        "colunas": colunas,
        "stages_nomes": _HOTEL_STAGE_LABELS,
        "menu_ativo": "kanban_hotel",
    }

    return render(request, "admin_custom/pipeline_hotel.html", context)


@login_required
@require_POST
def pipeline_hotel_mover(request):
    bloqueio = require_admin_or_operator(request)
    if bloqueio:
        return bloqueio
    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("{}")
        obj_id = payload.get("id", "")
        stage_destino = payload.get("stage_destino", "")
        moved_via = payload.get("moved_via", "button")
    else:
        obj_id = request.POST.get("id", "")
        stage_destino = request.POST.get("stage_destino", "")
        moved_via = request.POST.get("moved_via", "button")

    if moved_via not in {"drag", "button", "system"}:
        moved_via = "button"

    if not obj_id or stage_destino not in _HOTEL_STAGE_SLUGS:
        return HttpResponseBadRequest("Parametros invalidos")

    with transaction.atomic():
        obj = get_object_or_404(EmissaoHotel, pk=obj_id)
        ensure_company_access(request, obj)
        stage_origem = obj.status or "solicitado"

        if stage_destino not in HOTEL_TRANSICOES.get(stage_origem, set()):
            return JsonResponse({"erro": "Transicao nao permitida"}, status=409)

        obj.status = stage_destino
        obj.save(update_fields=["status"])

        StageTransition.objects.create(
            hotel=obj,
            stage_origem=stage_origem,
            stage_destino=stage_destino,
            moved_via=moved_via,
            user=request.user if request.user.is_authenticated else None,
        )

    if "application/json" in content_type:
        return JsonResponse({"ok": True, "stage_destino": stage_destino})
    return redirect("admin_pipeline_hotel")
