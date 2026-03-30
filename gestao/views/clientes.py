from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from ..forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
    EmissaoHotelForm,
    CotacaoVooForm,
    PassageiroFrequenteForm,
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
    PassageiroFrequente,
)
from gestao.utils import generate_unique_username, sync_cliente_activation
from gestao.services.dashboard import (
    build_operational_dashboard_context,
)
from gestao.services.cpf_limite import get_cpf_control_data
from .permissions import require_admin_or_operator

import csv
import json
from datetime import date, timedelta
from urllib.parse import urlencode


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
    status = request.GET.get("status", "")
    data_inicio = request.GET.get("data_inicio", "")
    data_fim = request.GET.get("data_fim", "")
    conta_id = request.GET.get("conta", "")

    management_context = build_operational_dashboard_context(user=request.user, request=request)
    management_dashboard = management_context["management_dashboard"]

    clientes = Cliente.objects.filter(perfil="cliente").select_related("usuario")
    if busca:
        clientes = clientes.filter(
            Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
            | Q(usuario__last_name__icontains=busca)
        )
    if status == "ativo":
        clientes = clientes.filter(ativo=True)
    elif status == "inativo":
        clientes = clientes.filter(ativo=False)
    start_date = None
    end_date = None
    try:
        if data_inicio:
            start_date = date.fromisoformat(data_inicio)
        if data_fim:
            end_date = date.fromisoformat(data_fim)
    except ValueError:
        start_date = None
        end_date = None
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
    if start_date:
        clientes = clientes.filter(usuario__date_joined__date__gte=start_date)
    if end_date:
        clientes = clientes.filter(usuario__date_joined__date__lte=end_date)
    if conta_id:
        clientes = clientes.filter(
            id__in=ContaFidelidade.objects.filter(
                id=conta_id,
                cliente__isnull=False,
            ).values_list("cliente_id", flat=True)
        )

    clientes = clientes.order_by("-usuario__date_joined", "usuario__username")
    total_clientes = clientes.count()
    clientes_ativos = clientes.filter(ativo=True).count()
    inicio_mes = timezone.localdate().replace(day=1)
    novos_mes = clientes.filter(usuario__date_joined__date__gte=inicio_mes).count()

    paginator = Paginator(clientes, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    displayed_count = len(page_obj.object_list)

    cliente_cards = []
    for cliente in page_obj.object_list:
        display_name = cliente.usuario.get_full_name() or cliente.usuario.username
        initials_source = [part[0].upper() for part in display_name.split()[:2] if part]
        initials = "".join(initials_source) or cliente.usuario.username[:2].upper()
        cliente_cards.append(
            {
                "id": cliente.id,
                "display_name": display_name,
                "username": cliente.usuario.username,
                "status_label": "Ativo" if cliente.ativo else "Inativo",
                "status_tone": "active" if cliente.ativo else "inactive",
                "initials": initials,
                "view_url": reverse("admin_visualizar_cliente", args=[cliente.id]),
                "edit_url": reverse("admin_editar_cliente", args=[cliente.id]),
            }
        )

    account_options = [
        {
            "id": str(conta.id),
            "label": f"{conta.programa.nome} - {(conta.cliente.usuario.get_full_name() or conta.cliente.usuario.username)}",
            "selected": str(conta.id) == conta_id,
        }
        for conta in ContaFidelidade.objects.filter(cliente__perfil="cliente")
        .select_related("cliente__usuario", "programa")
        .order_by("programa__nome", "cliente__usuario__username")
    ]

    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)

    def _page_url(number):
        params = pagination_params.copy()
        params["page"] = number
        encoded = params.urlencode()
        return f"?{encoded}" if encoded else f"?page={number}"

    empresa_id = request.GET.get("empresa_id", "")
    clear_filters_params = []
    if empresa_id:
        clear_filters_params.append(("empresa_id", empresa_id))
    clear_filters_url = f"?{urlencode(clear_filters_params)}" if clear_filters_params else request.path

    return render(
        request,
        "admin_custom/clientes.html",
        {
            "page_obj": page_obj,
            "cliente_cards": cliente_cards,
            "busca": busca,
            "status": status,
            "data_inicio": data_inicio or management_dashboard["start_date"],
            "data_fim": data_fim or management_dashboard["end_date"],
            "conta_id": conta_id,
            "account_options": account_options,
            "total_clientes": total_clientes,
            "clientes_ativos": clientes_ativos,
            "novos_mes": novos_mes,
            "displayed_count": displayed_count,
            "previous_page_url": _page_url(page_obj.previous_page_number()) if page_obj.has_previous() else "",
            "next_page_url": _page_url(page_obj.next_page_number()) if page_obj.has_next() else "",
            "clear_filters_url": clear_filters_url,
            "empresa_id": empresa_id,
            "management_dashboard": management_dashboard,
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
        request=request,
        cliente=cliente,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    passageiros = cliente.passageiros_frequentes.all().order_by("nome")
    passenger_cards = []
    type_labels = dict(PassageiroFrequente.TIPO_CHOICES)
    avatar_gradients = (
        "blue",
        "purple",
        "teal",
        "amber",
    )
    for index, passageiro in enumerate(passageiros):
        cpf_digits = "".join(filter(str.isdigit, passageiro.cpf or ""))
        if len(cpf_digits) == 11:
            cpf_display = f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
        else:
            cpf_display = passageiro.cpf or "--"
        parts = [part[0].upper() for part in passageiro.nome.split()[:2] if part]
        initials = "".join(parts) or passageiro.nome[:2].upper()
        passenger_cards.append(
            {
                "id": passageiro.id,
                "nome": passageiro.nome,
                "tipo_label": type_labels.get(passageiro.tipo, passageiro.tipo),
                "cpf": cpf_display,
                "data_nascimento": passageiro.data_nascimento.strftime("%d/%m/%Y") if passageiro.data_nascimento else "--",
                "relacao": passageiro.relacao or "--",
                "initials": initials,
                "avatar_tone": avatar_gradients[index % len(avatar_gradients)],
            }
        )

    total_preco_cheio = sum(float(e.valor_referencia or 0) for e in EmissaoPassagem.objects.filter(cliente=cliente))
    total_pago_cliente = sum(
        float((e.valor_total_final if e.valor_total_final not in (None, "") else (e.valor_venda_final or 0)) or 0)
        for e in EmissaoPassagem.objects.filter(cliente=cliente)
    )
    economia_cliente = total_preco_cheio - total_pago_cliente
    detail_kpis = list(context["management_dashboard"]["kpis"][:4])
    detail_kpis.append(
        {
            "titulo": "Economia acumulada",
            "valor": f"R$ {economia_cliente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "descricao": "Preco cheio menos valor pago nas emissoes.",
        }
    )
    passageiro_form = PassageiroFrequenteForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"add_passageiro", "edit_passageiro"}:
            instance = None
            if action == "edit_passageiro":
                instance = get_object_or_404(PassageiroFrequente, id=request.POST.get("passageiro_id"), cliente=cliente)
            passageiro_form = PassageiroFrequenteForm(request.POST, instance=instance)
            if passageiro_form.is_valid():
                passageiro = passageiro_form.save(commit=False)
                passageiro.cliente = cliente
                passageiro.save()
                messages.success(request, "Passageiro frequente salvo com sucesso.")
                return redirect("admin_visualizar_cliente", cliente_id=cliente.id)
        elif action == "delete_passageiro":
            passageiro = get_object_or_404(PassageiroFrequente, id=request.POST.get("passageiro_id"), cliente=cliente)
            passageiro.delete()
            messages.success(request, "Passageiro frequente removido com sucesso.")
            return redirect("admin_visualizar_cliente", cliente_id=cliente.id)

    context.update(
        {
            "cliente_obj": cliente,
            "passageiros_frequentes": passageiros,
            "passenger_cards": passenger_cards,
            "passageiro_form": passageiro_form,
            "passageiro_form_prefix": "passageiro-frequente",
            "economia_cliente": economia_cliente,
            "detail_kpis": detail_kpis,
            "cliente_back_url": reverse("admin_clientes"),
            "menu_ativo": "clientes",
        }
    )
    return render(request, "admin_custom/cliente_dashboard.html", context)
