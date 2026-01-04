from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..forms import CompanhiaAereaForm
from ..models import CompanhiaAerea

from .permissions import require_admin_or_operator


@login_required
def admin_companhias(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    busca = request.GET.get("busca", "")
    companhias = CompanhiaAerea.objects.all()
    if busca:
        companhias = companhias.filter(nome__icontains=busca)
    return render(
        request,
        "admin_custom/companhias.html",
        {"companhias": companhias, "busca": busca, "menu_ativo": "companhias"},
    )


@login_required
def criar_companhia(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    if request.method == "POST":
        form = CompanhiaAereaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_companhias")
    else:
        form = CompanhiaAereaForm()
    return render(
        request,
        "admin_custom/form_companhia_aerea.html",
        {"form": form, "menu_ativo": "companhias"},
    )


@login_required
def editar_companhia(request, companhia_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    companhia = get_object_or_404(CompanhiaAerea, id=companhia_id)
    if request.method == "POST":
        form = CompanhiaAereaForm(request.POST, instance=companhia)
        if form.is_valid():
            form.save()
            return redirect("admin_companhias")
    else:
        form = CompanhiaAereaForm(instance=companhia)
    return render(
        request,
        "admin_custom/form_companhia_aerea.html",
        {"form": form, "menu_ativo": "companhias"},
    )


@login_required
def deletar_companhia(request, companhia_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(
        getattr(request.user, "cliente_gestao", None), "perfil", ""
    )
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    CompanhiaAerea.objects.filter(id=companhia_id).delete()
    messages.success(request, "Companhia aérea deletada com sucesso.")
    return redirect("admin_companhias")
