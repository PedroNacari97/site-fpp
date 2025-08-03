from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect

from gestao.models import Empresa
from .forms import EmpresaForm, AdministradorForm


def superadmin_required(user):
    return user.is_superuser


@login_required
@user_passes_test(superadmin_required)
def empresa_list(request):
    empresas = Empresa.objects.all()
    return render(request, "superadmin/empresa_list.html", {"empresas": empresas})


@login_required
@user_passes_test(superadmin_required)
def empresa_create(request):
    if request.method == "POST":
        form = EmpresaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Empresa criada com sucesso.")
            return redirect("superadmin_empresa_list")
    else:
        form = EmpresaForm()
    return render(request, "superadmin/empresa_form.html", {"form": form})


@login_required
@user_passes_test(superadmin_required)
def administrador_create(request):
    if request.method == "POST":
        form = AdministradorForm(request.POST)
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Administrador criado com sucesso.")
            return redirect("superadmin_empresa_list")
    else:
        form = AdministradorForm()
    return render(request, "superadmin/administrador_form.html", {"form": form})
