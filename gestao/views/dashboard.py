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
    Empresa,
)
from ..services.dashboard import build_operational_dashboard_context
from ..value_utils import build_valor_milheiro_map, get_valor_referencia_from_map
from .permissions import require_admin_or_operator


def _default_metrics(total_titulares):
    return {
        "total_titulares": total_titulares,
        "total_emissoes": 0,
        "total_pontos": 0,
        "total_economizado": 0,
        "programas": [],
        "emissoes": {
            "qtd": 0,
            "pontos": 0,
            "valor_referencia": 0,
            "valor_taxas": 0,
            "custo_total": 0,
            "valor_economizado": 0,
        },
        "hoteis": {"qtd": 0, "valor_referencia": 0, "valor_pago": 0, "valor_economizado": 0},
        "emissoes_programa": [],
        "parceiros": {"lucro": 0, "vendas": 0, "milhas": 0, "valor_pago": 0, "valor_medio_milheiro": 0},
        "parceiros_cards": [],
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
    parceiros_cards = []

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
        emissoes_por_parceiro = {}
        for emissao in emissoes.select_related("emissor_parceiro"):
            emissor = emissao.emissor_parceiro
            if not emissor:
                continue
            entry = emissoes_por_parceiro.setdefault(
                emissor.id,
                {
                    "id": emissor.id,
                    "nome": emissor.nome,
                    "total_emissoes": 0,
                    "total_milhas": Decimal("0"),
                    "valor_pago": Decimal("0"),
                    "valor_medio_milheiro": Decimal("0"),
                },
            )
            entry["total_emissoes"] += 1
            entry["total_milhas"] += Decimal(emissao.pontos_utilizados or 0)
            entry["valor_pago"] += Decimal(emissao.custo_total or 0)
        for entry in emissoes_por_parceiro.values():
            if entry["total_milhas"]:
                entry["valor_medio_milheiro"] = entry["valor_pago"] / entry["total_milhas"]
        parceiros_cards = list(emissoes_por_parceiro.values())

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
    valor_taxas_emissoes = sum(float(e.valor_taxas or 0) for e in emissoes)
    custo_total_emissoes = sum(float(e.custo_total or 0) for e in emissoes)
    valor_economizado_emissoes = sum(float(e.economia_obtida or 0) for e in emissoes)
    total_pago_parceiro = Decimal("0")
    total_lucro = Decimal("0")
    total_vendas = Decimal("0")
    valor_medio_milheiro = Decimal("0")
    if view_type == "parceiros":
        total_milhas = Decimal("0")
        for emissao in emissoes:
            pontos = Decimal(emissao.pontos_utilizados or 0)
            total_pago_parceiro += Decimal(emissao.custo_total or 0)
            total_milhas += pontos
            if emissao.valor_venda_final is not None:
                total_vendas += Decimal(emissao.valor_venda_final or 0)
            total_lucro += Decimal(emissao.lucro or 0)
        if total_milhas:
            valor_medio_milheiro = total_pago_parceiro / total_milhas

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
    if view_type != "parceiros":
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
            "valor_taxas": valor_taxas_emissoes,
            "custo_total": custo_total_emissoes,
            "valor_economizado": valor_economizado_emissoes,
        },
        "hoteis": {
            "qtd": qtd_hoteis,
            "valor_referencia": valor_ref_hoteis,
            "valor_pago": valor_pago_hoteis,
            "valor_economizado": valor_economizado_hoteis,
        },
        "emissoes_programa": emissoes_programa,
        "parceiros": {
            "lucro": total_lucro,
            "vendas": total_vendas,
            "milhas": pontos_utilizados,
            "valor_pago": total_pago_parceiro,
            "valor_medio_milheiro": valor_medio_milheiro,
        },
        "parceiros_cards": parceiros_cards,
    }


@login_required
def admin_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = None
    empresa_id = request.GET.get("empresa_id")
    empresas = None
    if request.user.is_superuser:
        empresas = Empresa.objects.all().order_by("nome")
        if empresa_id:
            empresa = empresas.filter(id=empresa_id).first()
    else:
        empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)

    context = build_operational_dashboard_context(
        user=request.user,
        empresa=empresa,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    context.update(
        {
            "dashboard_base": "admin_custom/base_admin.html",
            "dashboard_title": "Dashboard Operacional",
            "dashboard_subtitle": "Visão operacional com alertas, emissões e ações prioritárias.",
            "menu_ativo": "dashboard",
            "empresas": empresas,
            "empresa_selecionada": empresa,
            "empresa_id": empresa_id,
        }
    )
    return render(request, "painel_cliente/dashboard.html", context)


@login_required
def api_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    view_type = request.GET.get("view", "clientes")
    entity_id = request.GET.get("cliente_id") if view_type == "clientes" else request.GET.get("conta_id") if view_type == "contas" else request.GET.get("emissor_id")
    data = build_dashboard_metrics(view_type, entity_id)
    return JsonResponse(data)
