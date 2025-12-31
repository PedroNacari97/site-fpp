from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render

from ..models import (
    Cliente,
    ContaAdministrada,
    ContaFidelidade,
    EmissaoHotel,
    EmissaoPassagem,
    EmissorParceiro,
)
from ..value_utils import build_valor_milheiro_map, get_valor_referencia_from_map
from .permissions import require_admin_or_operator


def _default_metrics(total_titulares):
    return {
        "total_titulares": total_titulares,
        "total_emissoes": 0,
        "total_pontos": 0,
        "total_economizado": 0,
        "programas": [],
        "emissoes": {"qtd": 0, "pontos": 0, "valor_referencia": 0, "valor_pago": 0, "valor_economizado": 0},
        "hoteis": {"qtd": 0, "valor_referencia": 0, "valor_pago": 0, "valor_economizado": 0},
        "emissoes_programa": [],
        "parceiros": {"lucro": 0, "vendas": 0},
    }


def build_dashboard_metrics(view_type="clientes", entity_id=None):
    clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True)
    contas_qs = ContaAdministrada.objects.filter(ativo=True)
    parceiros_qs = EmissorParceiro.objects.filter(ativo=True)

    contas = ContaFidelidade.objects.select_related(
        "programa", "programa__programa_base"
    )
    emissoes = EmissaoPassagem.objects.all()
    hoteis = EmissaoHotel.objects.all()

    if view_type == "clientes":
        contas = contas.filter(cliente__perfil="cliente", cliente__ativo=True, conta_administrada__isnull=True)
        emissoes = emissoes.filter(cliente__perfil="cliente", cliente__ativo=True)
        hoteis = hoteis.filter(cliente__perfil="cliente", cliente__ativo=True)
        if entity_id:
            cliente = clientes_qs.filter(id=entity_id).first()
            if not cliente:
                return _default_metrics(clientes_qs.count())
            contas = contas.filter(cliente_id=entity_id)
            emissoes = emissoes.filter(cliente_id=entity_id)
            hoteis = hoteis.filter(cliente_id=entity_id)
    elif view_type == "contas":
        contas = contas.filter(conta_administrada__isnull=False, conta_administrada__ativo=True)
        emissoes = emissoes.filter(conta_administrada__isnull=False)
        hoteis = hoteis.none()
        if entity_id:
            conta = contas_qs.filter(id=entity_id).first()
            if not conta:
                return _default_metrics(contas_qs.count())
            contas = contas.filter(conta_administrada_id=entity_id)
            emissoes = emissoes.filter(conta_administrada_id=entity_id)
    else:
        emissoes = emissoes.filter(emissor_parceiro__isnull=False)
        hoteis = hoteis.none()
        contas = contas.none()
        if entity_id:
            emissor = parceiros_qs.filter(id=entity_id).first()
            if not emissor:
                return _default_metrics(parceiros_qs.count())
            emissoes = emissoes.filter(emissor_parceiro_id=entity_id)

    programas_data = []
    total_pontos = 0
    if view_type in {"clientes", "contas"}:
        valor_referencia_map = build_valor_milheiro_map()
        total_pontos_unicos = {}
        for conta in contas:
            conta_base = conta.conta_saldo()
            pontos = conta_base.saldo_pontos
            valor_medio_programa = float(conta.valor_medio_por_mil or 0)
            valor_referencia_programa = float(
                get_valor_referencia_from_map(conta.programa, valor_referencia_map)
            )
            programas_data.append(
                {
                    "id": conta.programa.id,
                    "nome": conta.programa.nome,
                    "pontos": pontos,
                    "valor_total": (Decimal(pontos) / Decimal(1000))
                    * Decimal(valor_referencia_programa),
                    "valor_medio": valor_medio_programa,
                    "valor_referencia": valor_referencia_programa,
                    "conta_id": conta.id,
                    "conta_base_id": conta_base.id,
                }
            )
            total_pontos_unicos[conta_base.id] = pontos
        total_pontos = sum(total_pontos_unicos.values())

    total_emissoes = emissoes.count()
    pontos_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_ref_emissoes = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_pago_emissoes = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_economizado_emissoes = valor_ref_emissoes - valor_pago_emissoes

    qtd_hoteis = hoteis.count()
    valor_ref_hoteis = sum(float(h.valor_referencia or 0) for h in hoteis)
    valor_pago_hoteis = sum(float(h.valor_pago or 0) for h in hoteis)
    valor_economizado_hoteis = valor_ref_hoteis - valor_pago_hoteis

    total_titulares = {
        "clientes": clientes_qs.count(),
        "contas": contas_qs.count(),
        "parceiros": parceiros_qs.count(),
    }.get(view_type, 0)
    if entity_id:
        total_titulares = 1
    total_economizado = valor_economizado_emissoes + valor_economizado_hoteis
    total_vendas = sum(float(e.valor_venda_final or 0) for e in emissoes)
    total_lucro = sum(float(e.lucro or 0) for e in emissoes)

    emissoes_programa_qs = (
        emissoes.values("programa__nome").annotate(qtd=Count("id")).order_by("programa__nome")
    )
    emissoes_programa = [
        {"programa": e["programa__nome"] or "N/D", "quantidade": e["qtd"]}
        for e in emissoes_programa_qs
    ]

    return {
        "total_titulares": total_titulares,
        "total_emissoes": total_emissoes,
        "total_pontos": total_pontos,
        "total_economizado": total_economizado,
        "programas": programas_data,
        "emissoes": {
            "qtd": total_emissoes,
            "pontos": pontos_utilizados,
            "valor_referencia": valor_ref_emissoes,
            "valor_pago": valor_pago_emissoes,
            "valor_economizado": valor_economizado_emissoes,
        },
        "hoteis": {
            "qtd": qtd_hoteis,
            "valor_referencia": valor_ref_hoteis,
            "valor_pago": valor_pago_hoteis,
            "valor_economizado": valor_economizado_hoteis,
        },
        "emissoes_programa": emissoes_programa,
        "parceiros": {"lucro": total_lucro, "vendas": total_vendas},
    }


@login_required
def admin_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    view_type = request.GET.get("view", "clientes")
    cliente_id = request.GET.get("cliente_id")
    conta_id = request.GET.get("conta_id")
    emissor_id = request.GET.get("emissor_id")
    entity_id = cliente_id if view_type == "clientes" else conta_id if view_type == "contas" else emissor_id
    data = build_dashboard_metrics(view_type, entity_id)
    clientes = Cliente.objects.filter(perfil="cliente", ativo=True).order_by("usuario__first_name")
    contas_adm = ContaAdministrada.objects.filter(ativo=True).order_by("nome")
    emissores = EmissorParceiro.objects.filter(ativo=True).order_by("nome")
    selected_cliente = clientes.filter(id=cliente_id).first() if cliente_id else None
    selected_conta = contas_adm.filter(id=conta_id).first() if conta_id else None
    selected_emissor = emissores.filter(id=emissor_id).first() if emissor_id else None
    context = {
        **data,
        "clientes": clientes,
        "contas_administradas": contas_adm,
        "emissores_parceiros": emissores,
        "selected_cliente": selected_cliente,
        "selected_conta": selected_conta,
        "selected_emissor": selected_emissor,
        "view_type": view_type,
    }
    return render(request, "admin_custom/dashboard.html", context)


@login_required
def api_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    view_type = request.GET.get("view", "clientes")
    entity_id = request.GET.get("cliente_id") if view_type == "clientes" else request.GET.get("conta_id") if view_type == "contas" else request.GET.get("emissor_id")
    data = build_dashboard_metrics(view_type, entity_id)
    return JsonResponse(data)
