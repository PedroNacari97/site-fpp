from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ContaFidelidadeForm
from ..models import ContaFidelidade
from .permissions import require_admin_or_operator


@login_required
def criar_conta(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm()
    return render(request, "admin_custom/contas_form.html", {"form": form})


@login_required
def editar_conta(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(instance=conta)
    return render(request, "admin_custom/contas_form.html", {"form": form})


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
def admin_contas(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa").filter(
        cliente__perfil="cliente", cliente__ativo=True
    )
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
