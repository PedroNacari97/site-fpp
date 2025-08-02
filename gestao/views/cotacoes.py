from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from painel_cliente.views import build_dashboard_context
from django import forms
from django.db import models

from ..forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
    EmissaoHotelForm,
    CotacaoVooForm,
    CalculadoraCotacaoForm,
)
from django.contrib.auth.models import User
from ..models import (
    Cliente,
    ContaFidelidade,
    ProgramaFidelidade,
    EmissaoPassagem,
    Aeroporto,
    ValorMilheiro,
    EmissaoHotel,
    CotacaoVoo,
    Passageiro,
    Escala,
    CompanhiaAerea,
)
from ..pdf_cotacao import gerar_pdf_cotacao
from ..pdf_emissao import gerar_pdf_emissao
import csv
import json
from datetime import timedelta
from decimal import Decimal


def admin_required(user):
    return user.is_staff or user.is_superuser


# --- COTAÇÕES ---
@login_required
@user_passes_test(admin_required)
def admin_cotacoes(request):
    if request.method == "POST":
        programa_nome = request.POST.get("programa_nome")
        valor_mercado = request.POST.get("valor_mercado")
        if programa_nome and valor_mercado:
            ValorMilheiro.objects.update_or_create(
                programa_nome=programa_nome, defaults={"valor_mercado": valor_mercado}
            )
    cotacoes = ValorMilheiro.objects.all().order_by("programa_nome")
    programas = ProgramaFidelidade.objects.all()
    return render(
        request,
        "admin_custom/cotacoes.html",
        {
            "cotacoes": cotacoes,
            "programas": programas,
        },
    )



# --- COTAÇÕES DE VOO ---
@login_required
@user_passes_test(admin_required)
def admin_cotacoes_voo(request):
    cotacoes = CotacaoVoo.objects.all().select_related("cliente", "origem", "destino")
    return render(request, "admin_custom/cotacoes_voo.html", {"cotacoes": cotacoes})


@login_required
@user_passes_test(admin_required)
def nova_cotacao_voo(request):
    initial = {}
    emissao_id = request.GET.get("emissao")
    if emissao_id:
        emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
        initial = {
            "cliente": emissao.cliente_id,
            "companhia_aerea": emissao.companhia_aerea.nome if emissao.companhia_aerea else "",
            "origem": emissao.aeroporto_partida_id,
            "destino": emissao.aeroporto_destino_id,
            "data_ida": emissao.data_ida,
            "data_volta": emissao.data_volta,
            "programa": emissao.programa_id,
            "qtd_passageiros": emissao.qtd_passageiros,
        }
    if request.method == "POST":
        form = CotacaoVooForm(request.POST)
        if form.is_valid():
            cot = form.save()
            if cot.status == "emissao" and cot.emissao is None:
                emissao = EmissaoPassagem.objects.create(
                    cliente=cot.cliente,
                    aeroporto_partida=cot.origem,
                    aeroporto_destino=cot.destino,
                    data_ida=cot.data_ida,
                    data_volta=cot.data_volta,
                    programa=cot.programa,
                    qtd_passageiros=cot.qtd_passageiros,
                    companhia_aerea=CompanhiaAerea.objects.filter(nome=cot.companhia_aerea).first(),
                    valor_referencia=cot.valor_passagem,
                    valor_pago=cot.valor_vista,
                    pontos_utilizados=cot.milhas,
                    detalhes=cot.observacoes,
                )
                cot.emissao = emissao
                cot.save()
            return redirect("admin_cotacoes_voo")
    else:
        form = CotacaoVooForm(initial=initial)
    return render(request, "admin_custom/form_cotacao.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def editar_cotacao_voo(request, cotacao_id):
    cotacao = get_object_or_404(CotacaoVoo, id=cotacao_id)
    if request.method == "POST":
        form = CotacaoVooForm(request.POST, instance=cotacao)
        if form.is_valid():
            cot = form.save()
            if cot.status == "emissao" and cot.emissao is None:
                emissao = EmissaoPassagem.objects.create(
                    cliente=cot.cliente,
                    aeroporto_partida=cot.origem,
                    aeroporto_destino=cot.destino,
                    data_ida=cot.data_ida,
                    data_volta=cot.data_volta,
                    programa=cot.programa,
                    qtd_passageiros=cot.qtd_passageiros,
                    companhia_aerea=CompanhiaAerea.objects.filter(nome=cot.companhia_aerea).first(),
                    valor_referencia=cot.valor_passagem,
                    valor_pago=cot.valor_vista,
                    pontos_utilizados=cot.milhas,
                    detalhes=cot.observacoes,
                )
                cot.emissao = emissao
                cot.save()
            return redirect("admin_cotacoes_voo")
    else:
        form = CotacaoVooForm(instance=cotacao)
    return render(request, "admin_custom/form_cotacao.html", {"form": form})

@login_required
@user_passes_test(admin_required)
def admin_valor_milheiro(request):
    cotacoes = ValorMilheiro.objects.all().order_by("programa_nome")
    return render(request, "admin_custom/valor_milheiro.html", {"cotacoes": cotacoes})

@login_required
@user_passes_test(admin_required)
def cotacao_voo_pdf(request, cotacao_id):
    cotacao = get_object_or_404(CotacaoVoo, id=cotacao_id)
    pdf_content = gerar_pdf_cotacao(cotacao)
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cotacao_{cotacao_id}.pdf"'
    return response


@login_required
@user_passes_test(admin_required)
def calculadora_cotacao(request):
    resultado = None
    if request.method == 'POST':
        form = CalculadoraCotacaoForm(request.POST)
        if form.is_valid():
            milhas = form.cleaned_data['milhas']
            valor_milheiro = form.cleaned_data['valor_milheiro']
            taxas = form.cleaned_data['taxas']
            juros = form.cleaned_data['juros']
            desconto = form.cleaned_data['desconto']
            valor_passagem = form.cleaned_data['valor_passagem']
            parcelas = form.cleaned_data['parcelas'] or 1

            base = (Decimal(milhas) / Decimal('1000')) * Decimal(valor_milheiro) + Decimal(taxas)
            valor_parcelado = base * Decimal(juros)
            valor_vista = valor_parcelado * Decimal(desconto)
            economia = Decimal(valor_passagem) - valor_vista
            parcela = valor_parcelado / Decimal(parcelas)
            resultado = {
                'valor_parcelado': round(valor_parcelado, 2),
                'valor_vista': round(valor_vista, 2),
                'economia': round(economia, 2),
                'parcela': round(parcela, 2),
            }
    else:
        form = CalculadoraCotacaoForm()
    return render(request, 'admin_custom/calculadora_cotacao.html', {'form': form, 'resultado': resultado})

