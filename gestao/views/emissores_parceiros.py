from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import require_admin_or_operator
from ..forms import EmissorParceiroForm
from ..models import EmissaoPassagem, EmissorParceiro


@login_required
def admin_emissores_parceiros(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissores = EmissorParceiro.objects.all()
    if empresa:
        emissores = emissores.filter(empresa=empresa)
    search = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if search:
        emissores = emissores.filter(Q(nome__icontains=search) | Q(telefone__icontains=search))
    if status == "ativo":
        emissores = emissores.filter(ativo=True)
    elif status == "inativo":
        emissores = emissores.filter(ativo=False)
    return render(
        request,
        "admin_custom/emissores_parceiros.html",
        {
            "emissores": emissores,
            "menu_ativo": "emissores",
            "search": search,
            "status_filter": status,
        },
    )


@login_required
def criar_emissor_parceiro(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = EmissorParceiroForm(request.POST, empresa=empresa)
        if form.is_valid():
            emissor = form.save(commit=False)
            emissor.empresa = empresa
            emissor.save()
            form.save_m2m()
            return redirect("admin_emissores_parceiros")
    else:
        form = EmissorParceiroForm(empresa=empresa)
    return render(
        request,
        "admin_custom/form_emissor_parceiro.html",
        {"form": form, "menu_ativo": "emissores"},
    )


@login_required
def editar_emissor_parceiro(request, emissor_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissor = get_object_or_404(EmissorParceiro, id=emissor_id)
    if empresa and emissor.empresa != empresa:
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = EmissorParceiroForm(request.POST, instance=emissor, empresa=empresa)
        if form.is_valid():
            form.save()
            return redirect("admin_emissores_parceiros")
    else:
        form = EmissorParceiroForm(instance=emissor, empresa=empresa)
    return render(
        request,
        "admin_custom/form_emissor_parceiro.html",
        {"form": form, "menu_ativo": "emissores"},
    )


@login_required
def emissor_parceiro_movimentacoes(request, emissor_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissor = get_object_or_404(EmissorParceiro, id=emissor_id)
    if empresa and emissor.empresa != empresa:
        return render(request, "sem_permissao.html")
    emissoes = (
        EmissaoPassagem.objects.filter(emissor_parceiro=emissor)
        .select_related("aeroporto_partida", "aeroporto_destino")
        .order_by("-criado_em")
    )
    return render(
        request,
        "admin_custom/emissor_parceiro_movimentacoes.html",
        {
            "emissor": emissor,
            "emissoes": emissoes,
            "menu_ativo": "emissores",
        },
    )


@login_required
def deletar_emissor_parceiro(request, emissor_id):
    if request.method != "POST":
        return redirect("admin_emissores_parceiros")
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissor = get_object_or_404(EmissorParceiro, id=emissor_id)
    if empresa and emissor.empresa != empresa:
        return render(request, "sem_permissao.html")
    emissor.delete()
    messages.success(request, "Emissor parceiro deletado com sucesso.")
    return redirect("admin_emissores_parceiros")
