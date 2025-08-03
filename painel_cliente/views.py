from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from gestao.pdf_emissao import gerar_pdf_emissao
from gestao.models import ContaFidelidade, EmissaoPassagem, EmissaoHotel, Cliente

from .utils import generate_dashboard_context


@login_required
def dashboard_view(request):
    cliente = get_object_or_404(Cliente, usuario=request.user)
    if not cliente.ativo:
        return render(request, "painel_cliente/inativo.html")
    context = generate_dashboard_context(request.user)
    return render(request, "painel_cliente/dashboard.html", context)


@login_required
def list_account_movements(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id, cliente__usuario=request.user)
    movements = conta.movimentacoes.all().order_by("-data")
    return render(
        request,
        "painel_cliente/movimentacoes.html",
        {"movimentacoes": movements, "conta": conta},
    )


@login_required
def list_flight_emissions(request):
    conta = ContaFidelidade.objects.filter(cliente__usuario=request.user).first()
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    return render(
        request,
        "painel_cliente/emissoes.html",
        {"emissoes": emissoes, "conta": conta, "total_pago": total_pago},
    )


@login_required
def download_emission_pdf(request, emissao_id):
    emissao = get_object_or_404(
        EmissaoPassagem, id=emissao_id, cliente__usuario=request.user
    )
    pdf = gerar_pdf_emissao(emissao)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="emissao_{emissao.id}.pdf"'
    return response


@login_required
def list_hotel_emissions(request):
    emissoes = EmissaoHotel.objects.filter(cliente__usuario=request.user)
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
