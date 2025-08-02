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


def admin_required(user):
    return user.is_staff or user.is_superuser


# --- CONTAS ---
@login_required
@user_passes_test(admin_required)
def listar_contas(request):
    contas = ContaFidelidade.objects.all()
    return render(request, "admin_custom/contas_list.html", {"contas": contas})


@login_required
@user_passes_test(admin_required)
def criar_conta(request):
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm()
    return render(request, "admin_custom/contas_form.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def editar_conta(request, conta_id):
    conta = ContaFidelidade.objects.get(id=conta_id)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(instance=conta)
    return render(request, "admin_custom/contas_form.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def admin_contas(request):
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa")
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(programa__nome__icontains=busca)
        )
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "admin_custom/contas.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "total_contas": contas.count(),
        },
    )



# --- AEROPORTOS ---
@login_required
@user_passes_test(admin_required)
def admin_aeroportos(request):
    if request.method == "POST":
        form = AeroportoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm()
    aeroportos = Aeroporto.objects.all()
    return render(
        request,
        "admin_custom/aeroportos.html",
        {
            "form": form,
            "aeroportos": aeroportos,
        },
    )


@login_required
@user_passes_test(admin_required)
def editar_aeroporto(request, aeroporto_id):
    aeroporto = Aeroporto.objects.get(id=aeroporto_id)
    if request.method == "POST":
        form = AeroportoForm(request.POST, instance=aeroporto)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm(instance=aeroporto)
    return render(request, "admin_custom/aeroportos_form.html", {"form": form})


# --- DASHBOARD ---
@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    total_clientes = Cliente.objects.count()
    total_contas = ContaFidelidade.objects.count()
    total_emissoes = EmissaoPassagem.objects.count()
    total_pontos = sum([c.saldo_pontos for c in ContaFidelidade.objects.all()])
    total_hoteis = EmissaoHotel.objects.count()
    valor_hoteis = sum(float(h.valor_pago or 0) for h in EmissaoHotel.objects.all())
    cotacoes_mercado = ValorMilheiro.objects.all().order_by("programa_nome")
    return render(
        request,
        "admin_custom/dashboard.html",
        {
            "total_clientes": total_clientes,
            "total_contas": total_contas,
            "total_emissoes": total_emissoes,
            "total_pontos": total_pontos,
            "total_hoteis": total_hoteis,
            "valor_hoteis": valor_hoteis,
            "cotacoes_mercado": cotacoes_mercado,
        },
    )



def admin_movimentacoes(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    movimentacoes = conta.movimentacoes.all()  # Aqui está o segredo!
    return render(
        request,
        "admin_custom/movimentacoes.html",
        {
            "conta": conta,
            "movimentacoes": movimentacoes,
        },
    )


class NovaMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["data", "pontos", "valor_pago", "descricao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.TextInput(attrs={"placeholder": "Descrição"}),
        }


@staff_member_required
def admin_nova_movimentacao(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if not conta.cliente.ativo:
        return HttpResponse("Cliente inativo", status=403)
    if request.method == "POST":
        form = NovaMovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.conta = conta
            mov.save()
            return redirect("admin_movimentacoes", conta_id=conta.id)
    else:
        form = NovaMovimentacaoForm()
    return render(
        request,
        "admin_custom/nova_movimentacao.html",
        {
            "form": form,
            "conta": conta,
        },
    )


