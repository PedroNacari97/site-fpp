from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Case, When, DecimalField, Value
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
    InteresseViagemClienteForm,
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
    InteresseViagemCliente,
)
from gestao.utils import generate_unique_username, sync_cliente_activation
from gestao.services.dashboard import (
    build_operational_dashboard_context,
)
from gestao.services.cpf_limite import get_cpf_control_data
from .permissions import ensure_company_access, require_admin_or_operator, scope_queryset_to_company

import csv
import json
from datetime import date, timedelta
from urllib.parse import urlencode


User = get_user_model()

MONTH_LABELS = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}

SEMESTER_LABELS = {
    1: "1o semestre",
    2: "2o semestre",
}


def _format_interest_months(values):
    return [MONTH_LABELS.get(int(value), str(value)) for value in (values or [])]


def _format_interest_days(values):
    return [f"Dia {int(value):02d}" for value in (values or [])]


def _format_interest_semesters(values):
    return [SEMESTER_LABELS.get(int(value), str(value)) for value in (values or [])]


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
                        password=None,
                        first_name=form.cleaned_data.get("first_name", ""),
                        last_name=form.cleaned_data.get("last_name", ""),
                        email=form.cleaned_data.get("email", ""),
                    )
                    user.set_unusable_password()

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
    if (permission_denied := ensure_company_access(request, cliente)):
        return permission_denied
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

    clientes = scope_queryset_to_company(
        Cliente.objects.filter(perfil="cliente").select_related("usuario"),
        request,
        "empresa",
    )
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
        for conta in scope_queryset_to_company(
            ContaFidelidade.objects.filter(cliente__perfil="cliente")
            .select_related("cliente__usuario", "programa"),
            request,
            "cliente__empresa",
        )
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


@login_required
def programas_do_cliente(request, cliente_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    cliente = get_object_or_404(
        scope_queryset_to_company(Cliente.objects.filter(perfil="cliente"), request, "empresa"),
        pk=cliente_id,
    )
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
    cliente = get_object_or_404(
        scope_queryset_to_company(Cliente.objects.all(), request, "empresa"),
        id=cliente_id,
    )
    AcessoClienteLog.objects.create(admin=request.user, cliente=cliente)
    active_client_tab = request.GET.get("tab", "passageiros")
    if active_client_tab == "programas":
        active_client_tab = "contas"
    if active_client_tab not in {"passageiros", "interesses", "cotacoes", "contas", "emissoes"}:
        active_client_tab = "passageiros"
    context = build_operational_dashboard_context(
        user=request.user,
        request=request,
        cliente=cliente,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    passageiros = cliente.passageiros_frequentes.all().order_by("nome")
    interesses_viagem = cliente.interesses_viagem.all().order_by("-criado_em")
    cotacoes_cliente = (
        CotacaoVoo.objects.filter(cliente=cliente)
        .select_related("origem", "destino", "programa")
        .order_by("-criado_em")
    )
    contas_cliente = (
        ContaFidelidade.objects.filter(cliente=cliente)
        .select_related("programa")
        .order_by("programa__nome")
    )
    passenger_cards = []
    type_labels = dict(PassageiroFrequente.TIPO_CHOICES)
    avatar_gradients = (
        "blue",
        "purple",
        "teal",
        "amber",
    )

    def _format_cpf(cpf_raw):
        digits = "".join(filter(str.isdigit, cpf_raw or ""))
        if len(digits) == 11:
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return cpf_raw or "--"

    def _initials(nome):
        parts = [p[0].upper() for p in (nome or "").split()[:2] if p]
        return "".join(parts) or (nome or "?")[:2].upper()

    # Build titular card from the client itself
    titular_nome = cliente.usuario.get_full_name() or cliente.usuario.username
    titular_card = {
        "id": None,
        "is_titular": True,
        "nome": titular_nome,
        "tipo_label": "Titular (cliente)",
        "tipo": "",
        "cpf": _format_cpf(cliente.cpf or ""),
        "cpf_raw": cliente.cpf or "",
        "rg": "",
        "passaporte": "",
        "passaporte_validade": "",
        "data_nascimento": cliente.data_nascimento.strftime("%d/%m/%Y") if getattr(cliente, "data_nascimento", None) else "--",
        "data_nascimento_raw": cliente.data_nascimento.strftime("%Y-%m-%d") if getattr(cliente, "data_nascimento", None) else "",
        "relacao": "Titular",
        "initials": _initials(titular_nome),
        "avatar_tone": "orange",
    }

    for index, passageiro in enumerate(passageiros):
        passenger_cards.append(
            {
                "id": passageiro.id,
                "is_titular": False,
                "nome": passageiro.nome,
                "tipo_label": type_labels.get(passageiro.tipo, passageiro.tipo),
                "tipo": passageiro.tipo or "",
                "cpf": _format_cpf(passageiro.cpf or ""),
                "cpf_raw": passageiro.cpf or "",
                "rg": passageiro.rg or "",
                "passaporte": passageiro.passaporte or "",
                "passaporte_validade": passageiro.passaporte_validade.strftime("%Y-%m-%d") if getattr(passageiro, "passaporte_validade", None) else "",
                "data_nascimento": passageiro.data_nascimento.strftime("%d/%m/%Y") if passageiro.data_nascimento else "--",
                "data_nascimento_raw": passageiro.data_nascimento.strftime("%Y-%m-%d") if passageiro.data_nascimento else "",
                "relacao": passageiro.relacao or "--",
                "initials": _initials(passageiro.nome),
                "avatar_tone": avatar_gradients[index % len(avatar_gradients)],
            }
        )

    interest_cards = []
    for interesse in interesses_viagem:
        criteria = []
        if interesse.continente:
            criteria.append(interesse.continente)
        if interesse.pais:
            criteria.append(interesse.pais)
        if interesse.cidade_destino:
            criteria.append(interesse.cidade_destino)
        if interesse.origem:
            criteria.append(f"Saida {interesse.origem}")
        if interesse.destino:
            criteria.append(f"Chegada {interesse.destino}")

        preferences = []
        if interesse.programa_fidelidade:
            preferences.append(interesse.programa_fidelidade)
        if interesse.companhia_aerea:
            preferences.append(interesse.companhia_aerea)
        if interesse.classe:
            preferences.append(interesse.get_classe_display())

        time_windows = []
        if interesse.meses_ida:
            time_windows.append(
                {
                    "label": "Meses de ida",
                    "items": _format_interest_months(interesse.meses_ida),
                }
            )
        if interesse.meses_volta:
            time_windows.append(
                {
                    "label": "Meses de volta",
                    "items": _format_interest_months(interesse.meses_volta),
                }
            )
        if interesse.dias_ida:
            time_windows.append(
                {
                    "label": "Dias de ida",
                    "items": _format_interest_days(interesse.dias_ida),
                }
            )
        if interesse.dias_volta:
            time_windows.append(
                {
                    "label": "Dias de volta",
                    "items": _format_interest_days(interesse.dias_volta),
                }
            )
        if interesse.semestres_ida:
            time_windows.append(
                {
                    "label": "Semestres de ida",
                    "items": _format_interest_semesters(interesse.semestres_ida),
                }
            )
        if interesse.semestres_volta:
            time_windows.append(
                {
                    "label": "Semestres de volta",
                    "items": _format_interest_semesters(interesse.semestres_volta),
                }
            )

        interest_cards.append(
            {
                "id": interesse.id,
                "nome": interesse.nome or "Interesse sem titulo",
                "criterios": criteria or ["Qualquer destino e rota"],
                "preferencias": preferences or ["Qualquer programa, companhia e classe"],
                "janelas": time_windows or [{"label": "Janela", "items": ["Sem restricao de datas"]}],
                "status_label": "Ativo" if interesse.ativo else "Inativo",
                "status_tone": "active" if interesse.ativo else "inactive",
            }
        )

    cotacao_rows = []
    status_labels = dict(CotacaoVoo.STATUS_CHOICES)
    for cotacao in cotacoes_cliente:
        cotacao_rows.append(
            {
                "id": cotacao.id,
                "data": timezone.localtime(cotacao.criado_em).strftime("%d/%m/%Y"),
                "programa": cotacao.programa.nome if cotacao.programa else "--",
                "trecho": f"{cotacao.origem.sigla if cotacao.origem else '--'} -> {cotacao.destino.sigla if cotacao.destino else '--'}",
                "classe": cotacao.classe or "--",
                "valor": f"R$ {float(cotacao.valor_vista or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "status": status_labels.get(cotacao.status, cotacao.status),
                "view_url": reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]),
                "edit_url": reverse("admin_editar_cotacao_voo", args=[cotacao.id]),
            }
        )

    conta_rows = []
    for conta in contas_cliente:
        saldo_pontos = conta.saldo_pontos
        valor_pago = conta.valor_total_pago
        valor_medio_milheiro = conta.valor_medio_por_mil
        cpfs_total = conta.quantidade_cpfs_disponiveis
        cpfs_disponiveis = conta.cpfs_disponiveis
        conta_rows.append(
            {
                "id": conta.id,
                "programa": conta.programa.nome,
                "saldo": saldo_pontos,
                "valor_pago": f"R$ {valor_pago:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "valor_medio": f"R$ {valor_medio_milheiro:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "cpfs_total": "Ilimitado" if cpfs_total is None else cpfs_total,
                "cpfs_disponiveis": "Ilimitado" if cpfs_disponiveis is None else cpfs_disponiveis,
                "movimentacoes_url": reverse("admin_movimentacoes", args=[conta.id]),
            }
        )

    _stats = EmissaoPassagem.objects.filter(cliente=cliente).aggregate(
        total_preco=Sum("valor_referencia"),
        total_final=Sum(
            Case(
                When(valor_total_final__isnull=False, then="valor_total_final"),
                default="valor_venda_final",
                output_field=DecimalField(),
            )
        ),
    )
    total_preco_cheio = float(_stats["total_preco"] or 0)
    total_pago_cliente = float(_stats["total_final"] or 0)
    economia_cliente = total_preco_cheio - total_pago_cliente
    detail_kpis = list(context["management_dashboard"]["kpis"][:4])
    detail_kpis.append(
        {
            "titulo": "Economia acumulada",
            "valor": f"R$ {economia_cliente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "descricao": "Preco cheio menos valor pago nas emissoes.",
        }
    )

    def _tab_url(tab_name):
        params = request.GET.copy()
        params["tab"] = tab_name
        query = params.urlencode()
        return f"{request.path}?{query}" if query else request.path

    def _redirect_tab(tab_name):
        return redirect(f"{reverse('admin_visualizar_cliente', args=[cliente.id])}?tab={tab_name}")

    passageiro_form = PassageiroFrequenteForm()
    interesse_viagem_form = InteresseViagemClienteForm()
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
                return _redirect_tab("passageiros")
        elif action == "add_interesse_viagem":
            interesse_viagem_form = InteresseViagemClienteForm(request.POST)
            if interesse_viagem_form.is_valid():
                interesse = interesse_viagem_form.save(commit=False)
                interesse.cliente = cliente
                interesse.save()
                messages.success(request, "Interesse de viagem salvo com sucesso.")
                return _redirect_tab("interesses")
        elif action == "delete_passageiro":
            passageiro = get_object_or_404(PassageiroFrequente, id=request.POST.get("passageiro_id"), cliente=cliente)
            passageiro.delete()
            messages.success(request, "Passageiro frequente removido com sucesso.")
            return _redirect_tab("passageiros")
        elif action == "delete_interesse_viagem":
            interesse = get_object_or_404(
                InteresseViagemCliente,
                id=request.POST.get("interesse_id"),
                cliente=cliente,
            )
            interesse.delete()
            messages.success(request, "Interesse de viagem removido com sucesso.")
            return _redirect_tab("interesses")

    context.update(
        {
            "cliente_obj": cliente,
            "passageiros_frequentes": passageiros,
            "passenger_cards": passenger_cards,
            "titular_card": titular_card,
            "passageiro_form": passageiro_form,
            "passageiro_form_prefix": "passageiro-frequente",
            "interesses_viagem": interesses_viagem,
            "interest_cards": interest_cards,
            "interesse_viagem_form": interesse_viagem_form,
            "economia_cliente": economia_cliente,
            "detail_kpis": detail_kpis,
            "cliente_back_url": reverse("admin_clientes"),
            "active_client_tab": active_client_tab,
            "client_tab_urls": {
                "passageiros": _tab_url("passageiros"),
                "interesses": _tab_url("interesses"),
                "cotacoes": _tab_url("cotacoes"),
                "contas": _tab_url("contas"),
                "emissoes": _tab_url("emissoes"),
            },
            "cotacao_rows": cotacao_rows,
            "conta_rows": conta_rows,
            "menu_ativo": "clientes",
        }
    )
    return render(request, "admin_custom/cliente_dashboard.html", context)
