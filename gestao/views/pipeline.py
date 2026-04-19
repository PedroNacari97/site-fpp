import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from gestao.models import CotacaoVoo, EmissaoPassagem, StageTransition
from gestao.models.stage_transition import STAGES, TRANSICOES
from .permissions import require_admin_or_operator, scope_queryset_to_company, ensure_company_access


_STAGE_SLUGS = {s[0] for s in STAGES}
_STAGE_LABELS = {s[0]: s[1] for s in STAGES}


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


_TIPO_OPERACAO_BADGE = {
    "venda_direta": {"label": "Venda direta", "tone": "blue"},
    "intermediario": {"label": "Intermediario", "tone": "gold"},
    "concierge": {"label": "Concierge", "tone": "purple"},
    "emissor_parceiro": {"label": "Emissor parceiro", "tone": "green"},
}


def _tipo_operacao_badge(obj):
    codigo = getattr(obj, "tipo_operacao", "") or "venda_direta"
    return _TIPO_OPERACAO_BADGE.get(codigo) or {"label": codigo.replace("_", " ").title(), "tone": "blue"}


def _cotacao_card(obj):
    cliente = getattr(obj, "cliente", None)
    operador_user = getattr(obj, "criado_por", None)
    origem = getattr(obj, "origem", None)
    destino = getattr(obj, "destino", None)
    emissao = getattr(obj, "emissao", None)

    # Se tem emissao vinculada, usa dados dela para rota/data/valor
    if emissao and emissao.localizador:
        e_origem = getattr(emissao, "aeroporto_partida", None)
        e_destino = getattr(emissao, "aeroporto_destino", None)
        data = emissao.data_ida or obj.data_ida
        valor = emissao.valor_cobrado_cliente or emissao.valor_venda_final or emissao.valor_total_final or obj.valor_vista or obj.valor_passagem or 0
        loc_origem = getattr(e_origem, "iata", "") if e_origem else (getattr(origem, "iata", "") if origem else "\u2014")
        loc_destino = getattr(e_destino, "iata", "") if e_destino else (getattr(destino, "iata", "") if destino else "\u2014")
        badge = _tipo_operacao_badge(emissao)
    else:
        data = obj.data_ida
        valor = obj.valor_vista or obj.valor_passagem or 0
        loc_origem = getattr(origem, "iata", "") if origem else "\u2014"
        loc_destino = getattr(destino, "iata", "") if destino else "\u2014"
        badge = _tipo_operacao_badge(cliente) if cliente and getattr(cliente, "tipo_cliente", None) else {"label": "Pendente", "tone": "blue"}
        if cliente and getattr(cliente, "tipo_cliente", ""):
            tipo_cli = cliente.tipo_cliente
            if tipo_cli == "concierge":
                badge = {"label": "Concierge", "tone": "purple"}
            elif tipo_cli == "intermediario":
                badge = {"label": "Intermediario", "tone": "gold"}
            elif tipo_cli == "conta_administrada":
                badge = {"label": "Conta admin.", "tone": "green"}
            else:
                badge = {"label": "Passageiro direto", "tone": "blue"}

    return {
        "tipo": "cotacao",
        "id": obj.id,
        "cliente_nome": str(cliente) if cliente else "Sem cliente",
        "origem": loc_origem,
        "destino": loc_destino,
        "data_ida": data,
        "valor": valor,
        "programa": str(obj.programa) if obj.programa_id else "",
        "avatar": _avatar_info(operador_user),
        "url_detalhe": reverse("admin_visualizar_cotacao_voo", args=(obj.id,)) if _has_url("admin_visualizar_cotacao_voo") else "#",
        "tipo_op_label": badge["label"],
        "tipo_op_tone": badge["tone"],
        "convertida": bool(emissao and emissao.localizador),
    }


def _emissao_card(obj):
    cliente = getattr(obj, "cliente", None)
    operador_user = getattr(obj, "criado_por", None)
    origem = getattr(obj, "aeroporto_partida", None)
    destino = getattr(obj, "aeroporto_destino", None)
    valor = obj.valor_cobrado_cliente or obj.valor_venda_final or obj.valor_total_final or obj.valor_referencia or 0
    badge = _tipo_operacao_badge(obj)
    return {
        "tipo": "emissao",
        "id": obj.id,
        "cliente_nome": str(cliente) if cliente else "Sem cliente",
        "origem": getattr(origem, "iata", "") if origem else "\u2014",
        "destino": getattr(destino, "iata", "") if destino else "\u2014",
        "data_ida": obj.data_ida,
        "valor": valor,
        "programa": str(obj.programa) if obj.programa_id else "",
        "avatar": _avatar_info(operador_user),
        "url_detalhe": reverse("admin_editar_emissao", args=(obj.id,)) if _has_url("admin_editar_emissao") else "#",
        "tipo_op_label": badge["label"],
        "tipo_op_tone": badge["tone"],
        "convertida": False,
    }


def _has_url(name):
    try:
        reverse(name, args=(1,))
        return True
    except Exception:
        return False


@login_required
def pipeline_view(request):
    bloqueio = require_admin_or_operator(request)
    if bloqueio:
        return bloqueio
    tabela = request.GET.get("tabela", "admin_cotacoes_voo")
    hoje = timezone.now()

    cotacoes_base = CotacaoVoo.objects.select_related(
        "cliente__usuario", "cliente__criado_por", "programa", "origem", "destino", "cliente__empresa"
    )
    cotacoes_base = scope_queryset_to_company(cotacoes_base, request, "cliente__empresa", "conta_administrada__empresa")

    emissoes_base = EmissaoPassagem.objects.select_related(
        "cliente__usuario", "cliente__criado_por", "programa", "aeroporto_partida", "aeroporto_destino", "cliente__empresa"
    )
    emissoes_base = scope_queryset_to_company(
        emissoes_base,
        request,
        "cliente__empresa",
        "conta_administrada__empresa",
        "emissor_parceiro__empresa",
    )

    # Cotacoes por stage — cada deal aparece em UMA unica coluna
    novo_pedido = [_cotacao_card(c) for c in cotacoes_base.filter(status="pendente").order_by("-criado_em")[:100]]
    cotacao_enviada = [_cotacao_card(c) for c in cotacoes_base.filter(status="enviada").order_by("-criado_em")[:100]]
    aprovada = [_cotacao_card(c) for c in cotacoes_base.filter(status="aceita").order_by("-criado_em")[:100]]

    # Em emissao: cotacoes com status emissao que AINDA NAO tem localizador na emissao vinculada
    from django.db.models import Q
    em_emissao = [
        _cotacao_card(c) for c in cotacoes_base.filter(status="emissao").filter(
            Q(emissao__isnull=True) | Q(emissao__localizador="")
        ).order_by("-criado_em")[:100]
    ]

    # Emitida: cotacoes com status emissao + emissao com localizador + data futura
    emitida_qs = cotacoes_base.filter(
        status="emissao", emissao__isnull=False
    ).exclude(emissao__localizador="").filter(emissao__data_ida__gte=hoje).order_by("-emissao__data_ida")[:100]
    emitida = [_cotacao_card(c) for c in emitida_qs]

    # Finalizada: cotacoes com status emissao + emissao com localizador + data passada
    finalizada_qs = cotacoes_base.filter(
        status="emissao", emissao__isnull=False
    ).exclude(emissao__localizador="").filter(emissao__data_ida__lt=hoje).order_by("-emissao__data_ida")[:100]
    finalizada = [_cotacao_card(c) for c in finalizada_qs]

    # Emissoes standalone (sem cotacao vinculada) entram nas colunas emitida/finalizada
    emissoes_standalone = emissoes_base.filter(cotacaovoo__isnull=True).exclude(localizador="")
    emitida_emissoes = emissoes_standalone.filter(data_ida__gte=hoje).order_by("-data_ida")[:100]
    finalizada_emissoes = emissoes_standalone.filter(data_ida__lt=hoje).order_by("-data_ida")[:100]
    emitida = emitida + [_emissao_card(e) for e in emitida_emissoes]
    finalizada = finalizada + [_emissao_card(e) for e in finalizada_emissoes]

    # Emissoes sem localizador sem cotacao entram em em_emissao
    emissoes_em_preparacao = emissoes_base.filter(cotacaovoo__isnull=True).filter(localizador="").order_by("-criado_em")[:100]
    em_emissao = em_emissao + [_emissao_card(e) for e in emissoes_em_preparacao]

    # Cancelada
    cancelada = [_cotacao_card(c) for c in cotacoes_base.filter(status="rejeitada").order_by("-criado_em")[:100]]

    def _destinos_com_nome(stage_id):
        slugs = sorted(TRANSICOES.get(stage_id, set()))
        return [{"slug": s, "nome": _STAGE_LABELS.get(s, s)} for s in slugs]

    def _destinos_json(stage_id):
        return mark_safe(json.dumps(sorted(TRANSICOES.get(stage_id, set()))))

    colunas = [
        {"id": "novo_pedido", "nome": "Novo pedido", "acento": "primary", "cards": novo_pedido, "destinos": _destinos_com_nome("novo_pedido"), "destinos_json": _destinos_json("novo_pedido")},
        {"id": "cotacao_enviada", "nome": "Cotacao enviada", "acento": "info", "cards": cotacao_enviada, "destinos": _destinos_com_nome("cotacao_enviada"), "destinos_json": _destinos_json("cotacao_enviada")},
        {"id": "aprovada", "nome": "Aprovada", "acento": "success", "cards": aprovada, "destinos": _destinos_com_nome("aprovada"), "destinos_json": _destinos_json("aprovada")},
        {"id": "em_emissao", "nome": "Em emissao", "acento": "warning", "cards": em_emissao, "destinos": _destinos_com_nome("em_emissao"), "destinos_json": _destinos_json("em_emissao")},
        {"id": "emitida", "nome": "Emitida", "acento": "success", "cards": emitida, "destinos": _destinos_com_nome("emitida"), "destinos_json": _destinos_json("emitida")},
        {"id": "finalizada", "nome": "Finalizada", "acento": "muted", "cards": finalizada, "destinos": _destinos_com_nome("finalizada"), "destinos_json": _destinos_json("finalizada")},
        {"id": "cancelada", "nome": "Cancelada", "acento": "danger", "cards": cancelada, "destinos": _destinos_com_nome("cancelada"), "destinos_json": _destinos_json("cancelada")},
    ]

    context = {
        "colunas": colunas,
        "stages_nomes": _STAGE_LABELS,
        "menu_ativo": "kanban",
    }

    return render(request, "admin_custom/pipeline.html", context)


@login_required
@require_POST
def pipeline_mover(request):
    bloqueio = require_admin_or_operator(request)
    if bloqueio:
        return bloqueio
    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("{}")
        tipo = payload.get("tipo", "")
        obj_id = payload.get("id", "")
        stage_destino = payload.get("stage_destino", "")
        moved_via = payload.get("moved_via", "button")
    else:
        tipo = request.POST.get("tipo", "")
        obj_id = request.POST.get("id", "")
        stage_destino = request.POST.get("stage_destino", "")
        moved_via = request.POST.get("moved_via", "button")

    if moved_via not in {"drag", "button", "system"}:
        moved_via = "button"

    if tipo not in ("cotacao", "emissao") or not obj_id or stage_destino not in _STAGE_SLUGS:
        return HttpResponseBadRequest("Parametros invalidos")

    with transaction.atomic():
        if tipo == "cotacao":
            obj = get_object_or_404(CotacaoVoo, pk=obj_id)
            ensure_company_access(request, obj)
            stage_origem = _stage_cotacao(obj)
        else:
            obj = get_object_or_404(EmissaoPassagem, pk=obj_id)
            ensure_company_access(request, obj)
            stage_origem = _stage_emissao(obj)

        if stage_destino not in TRANSICOES.get(stage_origem, set()):
            return JsonResponse({"erro": "Transicao nao permitida"}, status=409)

        # Map stage back to model status
        if tipo == "cotacao":
            status_map = {
                "novo_pedido": "pendente",
                "cotacao_enviada": "enviada",
                "aprovada": "aceita",
                "em_emissao": "emissao",
                "cancelada": "rejeitada",
            }
            if stage_destino == "em_emissao" and not hasattr(obj, "emissao"):
                return JsonResponse({"erro": "Transicao requer emissao"}, status=409)
            obj.status = status_map.get(stage_destino, stage_destino)
            obj.save()
        else:
            if stage_destino == "emitida" and not obj.localizador:
                return JsonResponse({"erro": "Informe o localizador antes de emitir"}, status=400)
            obj.status = stage_destino
            obj.save()

        StageTransition.objects.create(
            cotacao=obj if tipo == "cotacao" else None,
            emissao=obj if tipo == "emissao" else None,
            stage_origem=stage_origem,
            stage_destino=stage_destino,
            moved_via=moved_via,
            user=request.user if request.user.is_authenticated else None,
        )

    if "application/json" in content_type:
        return JsonResponse({"ok": True, "stage_destino": stage_destino})
    return redirect("admin_pipeline")


def _stage_cotacao(obj):
    """Map cotacao.status to pipeline stage slug."""
    status = obj.status
    mapping = {
        "pendente": "novo_pedido",
        "enviada": "cotacao_enviada",
        "aceita": "aprovada",
        "emissao": "em_emissao",
        "rejeitada": "cancelada",
    }
    return mapping.get(status, status)


def _stage_emissao(obj):
    """Map emissao state to pipeline stage slug."""
    if not obj.localizador:
        return "em_emissao"
    if obj.data_ida and obj.data_ida >= timezone.now():
        return "emitida"
    return "finalizada"
