from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render

from ..models import Cliente, ContaFidelidade, EmissaoHotel, EmissaoPassagem
from .permissions import require_admin_or_operator


def build_dashboard_metrics(cliente_id=None):
    contas = ContaFidelidade.objects.select_related("programa")
    emissoes = EmissaoPassagem.objects.all()
    hoteis = EmissaoHotel.objects.all()

    if cliente_id:
        contas = contas.filter(cliente_id=cliente_id)
        emissoes = emissoes.filter(cliente_id=cliente_id)
        hoteis = hoteis.filter(cliente_id=cliente_id)

    programas_data = []
    for conta in contas:
        programas_data.append(
            {
                "id": conta.programa.id,
                "nome": conta.programa.nome,
                "pontos": conta.saldo_pontos,
                "valor_total": (
                    Decimal(conta.saldo_pontos) / Decimal(1000)
                )
                * Decimal(conta.valor_medio_por_mil)
                * conta.programa.preco_medio_milheiro,
                "valor_medio": conta.valor_medio_por_mil,
                "valor_referencia": conta.programa.preco_medio_milheiro,
                "conta_id": conta.id,
            }
        )

    total_pontos = sum(p["pontos"] for p in programas_data)

    total_emissoes = emissoes.count()
    pontos_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_ref_emissoes = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_pago_emissoes = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_economizado_emissoes = valor_ref_emissoes - valor_pago_emissoes

    qtd_hoteis = hoteis.count()
    valor_ref_hoteis = sum(float(h.valor_referencia or 0) for h in hoteis)
    valor_pago_hoteis = sum(float(h.valor_pago or 0) for h in hoteis)
    valor_economizado_hoteis = valor_ref_hoteis - valor_pago_hoteis

    total_clientes = Cliente.objects.count() if not cliente_id else 1
    total_economizado = valor_economizado_emissoes + valor_economizado_hoteis

    emissoes_programa_qs = (
        emissoes.values("programa__nome").annotate(qtd=Count("id")).order_by("programa__nome")
    )
    emissoes_programa = [
        {"programa": e["programa__nome"] or "N/D", "quantidade": e["qtd"]}
        for e in emissoes_programa_qs
    ]

    return {
        "total_clientes": total_clientes,
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
    }


@login_required
def admin_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    cliente_id = request.GET.get("cliente_id")
    data = build_dashboard_metrics(cliente_id)
    clientes = Cliente.objects.all().order_by("usuario__first_name")
    selected_cliente = Cliente.objects.filter(id=cliente_id).first() if cliente_id else None
    context = {**data, "clientes": clientes, "selected_cliente": selected_cliente}
    return render(request, "admin_custom/dashboard.html", context)


@login_required
def api_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    cliente_id = request.GET.get("cliente_id")
    data = build_dashboard_metrics(cliente_id)
    return JsonResponse(data)
