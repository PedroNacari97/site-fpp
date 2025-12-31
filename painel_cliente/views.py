"""Views for the Painel do Cliente app."""

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
import re

from services.pdf_service import emissao_pdf_response
from gestao.models import Cliente, Passageiro
from gestao.utils import normalize_cpf
from gestao.value_utils import build_valor_milheiro_map, get_valor_referencia_from_map
from repositories.painel_repository import (
    get_contas_by_user,
    get_emissoes_passagem_by_user,
    get_emissoes_hotel_by_user,
    get_conta_by_id_for_user,
    get_emissao_passagem_for_user,
)


EMISSAO_REGEX = re.compile(r"Emissão #(\d+)")


def _annotate_emissao_id(movimentacoes):
    movs = list(movimentacoes)
    for mov in movs:
        match = EMISSAO_REGEX.search(mov.descricao or "")
        mov.emissao_id = int(match.group(1)) if match else None
    return movs


def _annotate_cpf_consumo(movimentacoes):
    emissao_ids = [mov.emissao_id for mov in movimentacoes if mov.emissao_id]
    cpfs_por_emissao = {}
    if emissao_ids:
        passageiros = Passageiro.objects.filter(emissao_id__in=emissao_ids).values(
            "emissao_id", "cpf"
        )
        for row in passageiros:
            cpf = normalize_cpf(row.get("cpf") or "")
            if not cpf:
                continue
            cpfs_por_emissao.setdefault(row["emissao_id"], set()).add(cpf)
    for mov in movimentacoes:
        mov.cpfs_consumidos = len(cpfs_por_emissao.get(mov.emissao_id, set())) if mov.emissao_id else 0
    return movimentacoes

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
    valor_referencia_map = build_valor_milheiro_map()
    for conta in contas:
        saldo = conta.saldo_pontos or 0
        valor_medio = float(conta.valor_medio_por_mil or 0)
        valor_referencia = float(
            get_valor_referencia_from_map(conta.programa, valor_referencia_map)
        )
        valor_total = (saldo / 1000) * valor_referencia
        contas_info.append(
            {
                "id": conta.id,
                "programa": conta.programa.nome,
                "saldo_pontos": saldo,
                "valor_total": valor_total,
                "valor_medio": valor_medio,
                "valor_referencia": valor_referencia,
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
    movimentacoes = _annotate_cpf_consumo(
        _annotate_emissao_id(conta.movimentacoes_compartilhadas.order_by("-data"))
    )

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
