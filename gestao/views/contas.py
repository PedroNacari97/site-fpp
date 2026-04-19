from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ContaFidelidadeForm, ContaAdministradaForm
from ..models import ContaFidelidade, ContaAdministrada
from .permissions import ensure_company_access, require_admin_or_operator, scope_queryset_to_company


@login_required
def criar_conta(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, empresa=empresa)
        if form.is_valid():
            conta = form.save()
            if conta.conta_administrada_id:
                return redirect(
                    "admin_programas_da_conta_administrada",
                    conta_id=conta.conta_administrada_id,
                )
            return redirect("admin_contas")
    else:
        initial = {}
        if request.GET.get("conta_administrada"):
            initial["conta_administrada"] = request.GET.get("conta_administrada")
        form = ContaFidelidadeForm(empresa=empresa, initial=initial)
    return render(
        request,
        "admin_custom/contas_form.html",
        {"form": form, "menu_ativo": "contas"},
    )


@login_required
def criar_conta_administrada(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = ContaAdministradaForm(request.POST)
        if form.is_valid():
            conta = form.save(commit=False)
            conta.empresa = empresa
            conta.save()
            messages.success(request, "Conta administrada criada com sucesso.")
            return redirect("admin_contas_administradas")
    else:
        form = ContaAdministradaForm()
    return render(
        request,
        "admin_custom/contas_adm_form.html",
        {"form": form, "menu_ativo": "contas_adm"},
    )


@login_required
def editar_conta(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if (permission_denied := ensure_company_access(request, conta)):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, instance=conta, empresa=empresa)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(instance=conta, empresa=empresa)
    return render(
        request,
        "admin_custom/contas_form.html",
        {"form": form, "menu_ativo": "contas"},
    )


@login_required
def editar_conta_administrada(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(
        ContaAdministrada,
        id=conta_id,
        empresa=getattr(getattr(request.user, "cliente_gestao", None), "empresa", None),
    )
    if request.method == "POST":
        form = ContaAdministradaForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta administrada atualizada com sucesso.")
            return redirect("admin_contas_administradas")
    else:
        form = ContaAdministradaForm(instance=conta)
    return render(
        request,
        "admin_custom/contas_adm_form.html",
        {"form": form, "menu_ativo": "contas_adm"},
    )


@login_required
def deletar_conta(request, conta_id):
    if request.method != "POST":
        return redirect("admin_contas")
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    conta = get_object_or_404(
        scope_queryset_to_company(ContaFidelidade.objects.all(), request, "cliente__empresa", "conta_administrada__empresa"),
        id=conta_id,
    )
    conta.delete()
    messages.success(request, "Conta deletada com sucesso.")
    return redirect("admin_contas")


@login_required
def deletar_conta_administrada(request, conta_id):
    if request.method != "POST":
        return redirect("admin_contas_administradas")
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    ContaAdministrada.objects.filter(
        id=conta_id,
        empresa=getattr(getattr(request.user, "cliente_gestao", None), "empresa", None),
    ).delete()
    messages.success(request, "Conta administrada deletada com sucesso.")
    return redirect("admin_contas_administradas")


@login_required
def admin_contas(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    busca = request.GET.get("busca", "")
    contas = scope_queryset_to_company(
        ContaFidelidade.objects.select_related(
            "cliente__usuario",
            "conta_administrada",
            "conta_administrada__empresa",
            "programa",
        ).filter(
            Q(cliente__perfil="cliente", cliente__ativo=True)
            | Q(conta_administrada__isnull=False, conta_administrada__ativo=True)
        ),
        request,
        "cliente__empresa",
        "conta_administrada__empresa",
    )
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(cliente__usuario__last_name__icontains=busca)
            | Q(conta_administrada__nome__icontains=busca)
            | Q(programa__nome__icontains=busca)
        )
    contas = contas.order_by(
        "cliente__usuario__first_name",
        "cliente__usuario__username",
        "conta_administrada__nome",
        "programa__nome",
    )
    total_contas = contas.count()
    distinct_programas = contas.values("programa_id").distinct().count()
    titulares_ativos = (
        contas.filter(cliente__isnull=False).values("cliente_id").distinct().count()
        + contas.filter(conta_administrada__isnull=False)
        .values("conta_administrada_id")
        .distinct()
        .count()
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
            "total_contas": total_contas,
            "distinct_programas": distinct_programas,
            "titulares_ativos": titulares_ativos,
            "displayed_count": len(page_obj.object_list),
            "menu_ativo": "contas",
        },
    )


@login_required
def admin_contas_administradas(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    busca = request.GET.get("busca", "")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    contas = (
        ContaAdministrada.objects.filter(ativo=True)
        .select_related("empresa")
        .prefetch_related(
            "contas_fidelidade__programa",
            "contas_fidelidade__movimentacoes",
            "contas_fidelidade__usos_cpf",
        )
    )
    if empresa:
        contas = contas.filter(empresa=empresa)
    if busca:
        contas = contas.filter(
            Q(nome__icontains=busca)
            | Q(contas_fidelidade__programa__nome__icontains=busca)
        )
    contas = contas.distinct().order_by("nome")
    total_contas = contas.count()
    total_programas = ContaFidelidade.objects.filter(
        conta_administrada__in=contas
    ).count()
    contas_sem_programa = contas.filter(contas_fidelidade__isnull=True).count()
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    page_rows = [_build_conta_administrada_row(conta) for conta in page_obj.object_list]
    return render(
        request,
        "admin_custom/contas_administradas.html",
        {
            "page_obj": page_obj,
            "page_rows": page_rows,
            "busca": busca,
            "total_contas": total_contas,
            "total_programas": total_programas,
            "contas_sem_programa": contas_sem_programa,
            "menu_ativo": "contas_adm",
        },
    )


def _build_conta_administrada_row(conta):
    programas = list(conta.contas_fidelidade.all())
    saldo_total = sum(programa.saldo_pontos for programa in programas)
    valor_total = sum(programa.valor_total_pago for programa in programas)
    cpfs_usados = sum(programa.cpfs_usados for programa in programas)
    limites = [programa.limite_cpfs for programa in programas]
    limite_total = (
        None
        if programas and any(limite is None for limite in limites)
        else sum(limites)
    )
    cpfs_disponiveis = None if limite_total is None else max(limite_total - cpfs_usados, 0)

    if not programas:
        status = {"tone": "sem-programa", "label": "Sem programa"}
    elif any(programa.status_cpf["tone"] == "bloqueado" for programa in programas):
        status = {"tone": "bloqueado", "label": "Bloqueado"}
    elif any(programa.status_cpf["tone"] == "proximo" for programa in programas):
        status = {"tone": "proximo", "label": "Proximo do limite"}
    else:
        status = {"tone": "disponivel", "label": "Disponivel"}

    return {
        "conta": conta,
        "programas": programas,
        "programas_count": len(programas),
        "programas_nomes": ", ".join(programa.programa.nome for programa in programas)
        or "Nenhum programa vinculado",
        "saldo_pontos": saldo_total,
        "valor_total_pago": valor_total,
        "cpfs_usados": cpfs_usados,
        "limite_cpfs": limite_total,
        "cpfs_disponiveis": cpfs_disponiveis,
        "status": status,
    }


@login_required
def programas_da_conta_administrada(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    conta = get_object_or_404(
        ContaAdministrada.objects.select_related("empresa"),
        id=conta_id,
        empresa=empresa,
    )
    # âœ… CORREÃ‡ÃƒO: Adicionar order_by para consistÃªncia
    contas = ContaFidelidade.objects.filter(conta_administrada=conta).select_related("programa").order_by("programa__nome")
    lista_contas = []
    for c in contas:
        lista_contas.append(
            {
                "conta": c,
                "saldo_pontos": c.saldo_pontos,
                "valor_pago": c.valor_total_pago,
                "valor_medio_milheiro": c.valor_medio_por_mil,
                "cpfs_usados": c.cpfs_utilizados,
                "cpfs_total": c.quantidade_cpfs_disponiveis,
                "cpfs_disponiveis": c.cpfs_disponiveis,
            }
        )
    return render(
        request,
        "admin_custom/programas_da_conta_administrada.html",
        {
            "conta": conta,
            "lista_contas": lista_contas,
            "menu_ativo": "contas_adm",
        },
    )
