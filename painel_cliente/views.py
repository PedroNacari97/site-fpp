"""Views for the Painel do Cliente app."""

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from services.pdf_service import emissao_pdf_response
from gestao.models import Cliente
from repositories.painel_repository import (
    get_contas_by_user,
    get_emissoes_passagem_by_user,
    get_emissoes_hotel_by_user,
    get_conta_by_id_for_user,
    get_emissao_passagem_for_user,
)

@login_required
def sair(request):
    """Logout the current user and redirect to login."""
    logout(request)
    return redirect("/login/")


def build_dashboard_context(user):
    """Build context data for the dashboard page."""
    contas = get_contas_by_user(user)
    emissoes = get_emissoes_passagem_by_user(user)
    hoteis = get_emissoes_hotel_by_user(user)

    contas_info = []
    for conta in contas:
        saldo = conta.saldo_pontos or 0
        valor_medio = conta.valor_medio_por_mil or 0
        valor_total = (saldo / 1000) * valor_medio
        contas_info.append(
            {
                "id": conta.id,
                "programa": conta.programa.nome,
                "saldo_pontos": saldo,
                "valor_total": valor_total,
                "valor_medio": valor_medio,
                "valor_referencia": conta.programa.preco_medio_milheiro,
            }
        )

    return {
        "contas_info": contas_info,
        "qtd_emissoes": emissoes.count(),
        "pontos_totais_utilizados": sum(e.pontos_utilizados or 0 for e in emissoes),
        "valor_total_referencia": sum(float(e.valor_referencia or 0) for e in emissoes),
        "valor_total_pago": sum(float(e.valor_pago or 0) for e in emissoes),
        "valor_total_economizado": sum(float(e.valor_referencia or 0) for e in emissoes)
        - sum(float(e.valor_pago or 0) for e in emissoes),
        "qtd_hoteis": hoteis.count(),
        "valor_total_hoteis": sum(float(h.valor_pago or 0) for h in hoteis),
        "valor_total_hoteis_referencia": sum(
            float(h.valor_referencia or 0) for h in hoteis
        ),
        "valor_total_hoteis_economia": sum(
            float(h.economia_obtida or (h.valor_referencia - h.valor_pago))
            for h in hoteis
        ),
    }


@login_required
def dashboard(request):
    """Render the main dashboard for an authenticated client."""
    cliente = get_object_or_404(Cliente, usuario=request.user)
    if not cliente.ativo:
        return render(request, "painel_cliente/inativo.html")
    context = build_dashboard_context(request.user)
    return render(request, "painel_cliente/dashboard.html", context)


@login_required
def movimentacoes_programa(request, conta_id):
    """List points transactions for a fidelity account."""
    conta = get_conta_by_id_for_user(conta_id, request.user)
    movimentacoes = conta.movimentacoes.all().order_by("-data")

    return render(
        request,
        "painel_cliente/movimentacoes.html",
        {
            "movimentacoes": movimentacoes,
            "conta": conta,
        },
    )


@login_required
def painel_emissoes(request):
    """Display detailed flight emissions for the user."""
    conta = get_contas_by_user(request.user).first()
    emissoes = get_emissoes_passagem_by_user(request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    return render(
        request,
        "painel_cliente/emissoes.html",
        {
            "emissoes": emissoes,
            "conta": conta,
            "total_pago": total_pago,
        },
    )


@login_required
def emissao_pdf(request, emissao_id):
    """Download da emissão em formato PDF.

    A lógica de geração do PDF foi extraída para ``services.pdf_service``
    para manter a view responsável apenas pelo fluxo HTTP.
    """
    emissao = get_emissao_passagem_for_user(emissao_id, request.user)
    return emissao_pdf_response(emissao)


@login_required
def painel_hoteis(request):
    """Display hotel reservations for the user."""
    emissoes = get_emissoes_hotel_by_user(request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    total_economia = sum(
        float(e.economia_obtida or (e.valor_referencia - e.valor_pago))
        for e in emissoes
    )
    return render(
        request,
        "painel_cliente/hoteis.html",
        {
            "emissoes": emissoes,
            "total_pago": total_pago,
            "total_referencia": total_referencia,
            "total_economia": total_economia,
        },
    )
