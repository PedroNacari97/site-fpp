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


# --- CLIENTES ---
@login_required
@user_passes_test(admin_required)
def criar_cliente(request):
    if request.method == "POST":
        form = NovoClienteForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data.get("first_name", ""),
                last_name=form.cleaned_data.get("last_name", ""),
                email=form.cleaned_data.get("email", ""),
            )
            perfil = form.cleaned_data["perfil"]
            if perfil in ["admin", "operador"]:
                user.is_staff = True
            if perfil == "admin":
                user.is_superuser = True
            user.save()
            Cliente.objects.create(
                usuario=user,
                telefone=form.cleaned_data["telefone"],
                data_nascimento=form.cleaned_data["data_nascimento"],
                cpf=form.cleaned_data["cpf"],
                perfil=perfil,
                observacoes=form.cleaned_data["observacoes"],
                ativo=form.cleaned_data["ativo"],
            )
            return redirect("admin_clientes")
    else:
        form = NovoClienteForm()
    return render(request, "admin_custom/form_cliente.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def editar_cliente(request, cliente_id):
    cliente = Cliente.objects.get(id=cliente_id)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect("admin_clientes")
    else:
        form = ClienteForm(instance=cliente)
    return render(request, "admin_custom/form_cliente.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def admin_clientes(request):
    if "toggle" in request.GET:
        if not request.user.is_superuser:
            return HttpResponse("Sem permissão", status=403)
        cli = Cliente.objects.get(id=request.GET["toggle"])
        cli.ativo = not cli.ativo
        cli.save()
        return redirect("admin_clientes")

    busca = request.GET.get("busca", "")
    clientes = Cliente.objects.all().select_related("usuario")
    if busca:
        clientes = clientes.filter(
            Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
        )
    paginator = Paginator(clientes, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "admin_custom/clientes.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "total_clientes": clientes.count(),
        },
    )


def programas_do_cliente(request, cliente_id):
    cliente = Cliente.objects.get(pk=cliente_id)
    contas = ContaFidelidade.objects.filter(cliente=cliente)

    lista_contas = []
    for conta in contas:
        saldo_pontos = (
            conta.movimentacoes.aggregate(total=models.Sum("pontos"))["total"] or 0
        )
        valor_pago = (
            conta.movimentacoes.aggregate(total=models.Sum("valor_pago"))["total"] or 0
        )

        # Preço médio por milheiro
        if saldo_pontos and valor_pago:
            valor_medio_milheiro = (valor_pago / saldo_pontos) * 1000
        else:
            valor_medio_milheiro = 0

        lista_contas.append(
            {
                "conta": conta,
                "saldo_pontos": saldo_pontos,
                "valor_pago": valor_pago,
                "valor_medio_milheiro": valor_medio_milheiro,
            }
        )

    return render(
        request,
        "admin_custom/programas_do_cliente.html",
        {
            "cliente": cliente,
            "lista_contas": lista_contas,
        },
    )
@login_required
@user_passes_test(admin_required)
def visualizar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    AcessoClienteLog.objects.create(admin=request.user, cliente=cliente)
    context = build_dashboard_context(cliente.usuario)
    context["cliente_obj"] = cliente
    return render(request, "admin_custom/cliente_dashboard.html", context)

