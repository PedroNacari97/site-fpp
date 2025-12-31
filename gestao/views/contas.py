from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ContaFidelidadeForm, ContaAdministradaForm
from ..models import ContaFidelidade, ContaAdministrada
from .permissions import require_admin_or_operator


@login_required
def criar_conta(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, empresa=empresa)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(empresa=empresa)
    return render(request, "admin_custom/contas_form.html", {"form": form})


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
    return render(request, "admin_custom/contas_adm_form.html", {"form": form})


@login_required
def editar_conta(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, instance=conta, empresa=empresa)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(instance=conta, empresa=empresa)
    return render(request, "admin_custom/contas_form.html", {"form": form})


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
    return render(request, "admin_custom/contas_adm_form.html", {"form": form})


@login_required
def deletar_conta(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    ContaFidelidade.objects.filter(id=conta_id).delete()
    messages.success(request, "Conta deletada com sucesso.")
    return redirect("admin_contas")


@login_required
def deletar_conta_administrada(request, conta_id):
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
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa").filter(
        cliente__perfil="cliente", cliente__ativo=True, conta_administrada__isnull=True
    )
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(programa__nome__icontains=busca)
        )
    # ✅ CORREÇÃO: Adicionar order_by para evitar UnorderedObjectListWarning
    contas = contas.order_by("cliente__usuario__first_name", "programa__nome")
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


@login_required
def admin_contas_administradas(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    busca = request.GET.get("busca", "")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    contas = (
        ContaFidelidade.objects.filter(
            conta_administrada__isnull=False,
            conta_administrada__ativo=True,
        )
        .select_related("conta_administrada__empresa", "programa")
        .prefetch_related("movimentacoes")
    )
    if empresa:
        contas = contas.filter(conta_administrada__empresa=empresa)
    if busca:
        contas = contas.filter(
            Q(conta_administrada__nome__icontains=busca)
            | Q(programa__nome__icontains=busca)
        )
    # ✅ CORREÇÃO: Adicionar order_by para evitar UnorderedObjectListWarning
    contas = contas.order_by("conta_administrada__nome", "programa__nome")
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "admin_custom/contas_administradas.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "total_contas": contas.count(),
        },
    )


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
    # ✅ CORREÇÃO: Adicionar order_by para consistência
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
                "cpfs_total": c.programa.quantidade_cpfs_disponiveis,
                "cpfs_disponiveis": c.cpfs_disponiveis,
            }
        )
    return render(
        request,
        "admin_custom/programas_da_conta_administrada.html",
        {
            "conta": conta,
            "lista_contas": lista_contas,
        },
    )
