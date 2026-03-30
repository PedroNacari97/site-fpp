from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from accounts.access import user_has_admin_panel_access

from ..forms import EmpresaForm
from ..models import Cliente, Empresa


def require_superadmin(request):
    if not request.user.is_superuser or not user_has_admin_panel_access(request.user):
        return render(request, "sem_permissao.html")
    return None


@login_required
def empresas_list(request):
    if (permission_denied := require_superadmin(request)):
        return permission_denied
    empresas = Empresa.objects.all().select_related("admin__usuario")
    empresas_info = []
    total_operadores = 0
    total_clientes = 0
    empresas_ativas = 0
    for empresa in empresas:
        operadores = Cliente.objects.filter(empresa=empresa, perfil="operador").count()
        clientes = Cliente.objects.filter(empresa=empresa, perfil="cliente").count()
        total_operadores += operadores
        total_clientes += clientes
        if empresa.ativo:
            empresas_ativas += 1
        empresas_info.append(
            {
                "empresa": empresa,
                "operadores": operadores,
                "clientes": clientes,
            }
        )
    return render(
        request,
        "admin_custom/empresas.html",
        {
            "empresas_info": empresas_info,
            "totais": {
                "empresas": len(empresas_info),
                "ativas": empresas_ativas,
                "operadores": total_operadores,
                "clientes": total_clientes,
            },
            "menu_ativo": "empresas",
        },
    )


@login_required
def criar_empresa(request):
    if (permission_denied := require_superadmin(request)):
        return permission_denied
    if request.method == "POST":
        form = EmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save(criado_por=request.user)
            messages.success(request, f"Empresa {empresa.nome} criada com sucesso.")
            return redirect("admin_empresas")
    else:
        form = EmpresaForm()
    return render(
        request,
        "admin_custom/empresa_form.html",
        {"form": form, "menu_ativo": "empresas"},
    )
