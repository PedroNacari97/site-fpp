from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

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
    AcessoClienteLog,
)
from gestao.utils import generate_unique_username, sync_cliente_activation
from gestao.services.dashboard import build_operational_dashboard_context
from .permissions import require_admin_or_operator

import csv
import json
from datetime import timedelta


User = get_user_model()


# --- CLIENTES ---
@login_required
def criar_cliente(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    if request.method == "POST":
        form = NovoClienteForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    username = generate_unique_username()
                    cpf = form.cleaned_data.get("cpf")
                    user = User.objects.create_user(
                        username=username,
                        password=form.cleaned_data["password"],
                        first_name=form.cleaned_data.get("first_name", ""),
                        last_name=form.cleaned_data.get("last_name", ""),
                        email=form.cleaned_data.get("email", ""),
                    )

                    user.is_active = form.cleaned_data.get("ativo", True)
                    perfil = form.cleaned_data["perfil"]
                    if perfil in ["admin", "operador"]:
                        user.is_staff = True
                    user.save()

                    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
                    Cliente.objects.create(
                        usuario=user,
                        telefone=form.cleaned_data.get("telefone", ""),
                        data_nascimento=form.cleaned_data.get("data_nascimento"),
                        cpf=cpf,
                        perfil=perfil,
                        empresa=empresa,
                        observacoes=form.cleaned_data.get("observacoes", ""),
                        ativo=form.cleaned_data.get("ativo", True),
                        criado_por=request.user if request.user.is_authenticated else None,
                    )

                messages.success(request, "Cliente criado com sucesso.")
                return redirect("admin_clientes")

            except IntegrityError:
                form.add_error(None, "Erro ao criar usuário. Tente novamente.")
    else:
        form = NovoClienteForm()

    return render(
        request,
        "admin_custom/form_cliente.html",
        {"form": form, "menu_ativo": "clientes"},
    )


@login_required
def editar_cliente(request, cliente_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            old_ativo = cliente.ativo
            cliente = form.save()
            if old_ativo != cliente.ativo:
                sync_cliente_activation(cliente)
            return redirect("admin_clientes")
    else:
        form = ClienteForm(instance=cliente)
    return render(
        request,
        "admin_custom/form_cliente.html",
        {"form": form, "menu_ativo": "clientes"},
    )


@login_required
def admin_clientes(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied

    if "toggle" in request.GET:
        if not request.user.is_superuser:
            return HttpResponse("Sem permissão", status=403)
        cli = get_object_or_404(Cliente, id=request.GET["toggle"])
        cli.ativo = not cli.ativo
        cli.save(update_fields=["ativo"])
        sync_cliente_activation(cli)
        return redirect("admin_clientes")

    busca = request.GET.get("busca", "")
    clientes = Cliente.objects.filter(perfil="cliente").select_related("usuario")
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
            "menu_ativo": "clientes",
        },
    )


def programas_do_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id, perfil="cliente")
    contas = ContaFidelidade.objects.filter(cliente=cliente)

    lista_contas = []
    for conta in contas:
        saldo_pontos = conta.saldo_pontos
        valor_pago = conta.valor_total_pago
        valor_medio_milheiro = conta.valor_medio_por_mil
        cpfs_usados = conta.cpfs_utilizados
        cpfs_total = conta.quantidade_cpfs_disponiveis
        cpfs_disponiveis = conta.cpfs_disponiveis

        lista_contas.append(
            {
                "conta": conta,
                "saldo_pontos": saldo_pontos,
                "valor_pago": valor_pago,
                "valor_medio_milheiro": valor_medio_milheiro,
                "cpfs_usados": cpfs_usados,
                "cpfs_total": cpfs_total,
                "cpfs_disponiveis": cpfs_disponiveis,
            }
        )

    return render(
        request,
        "admin_custom/programas_do_cliente.html",
        {
            "cliente": cliente,
            "lista_contas": lista_contas,
            "menu_ativo": "clientes",
        },
    )


@login_required
def visualizar_cliente(request, cliente_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    cliente = get_object_or_404(Cliente, id=cliente_id)
    AcessoClienteLog.objects.create(admin=request.user, cliente=cliente)
    context = build_operational_dashboard_context(
        user=request.user,
        cliente=cliente,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    context.update(
        {
            "cliente_obj": cliente,
            "dashboard_base": "admin_custom/base_admin.html",
            "dashboard_title": f"Painel do Cliente: {cliente}",
            "dashboard_subtitle": "Visualização operacional do cliente com alertas e emissões.",
            "menu_ativo": "clientes",
        }
    )
    return render(request, "painel_cliente/dashboard.html", context)
