from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from gestao.models import Cliente, Empresa
from .forms import UsuarioForm, ClientePublicoForm
from gestao.utils import normalize_cpf

def custom_login(request):
    if request.method == "POST":
        identifier = request.POST.get("identifier")
        password = request.POST.get("password")
        perfil = request.POST.get("perfil")

        cpf = normalize_cpf(identifier)
        user = authenticate(request, cpf=cpf, password=password)
        if not user and perfil == "superadmin":
            user = authenticate(request, username=identifier, password=password)
        if user:
            login(request, user)
            user_perfil = getattr(getattr(user, "cliente_gestao", None), "perfil", "")
            if perfil == "superadmin" and user.is_superuser:
                 return redirect('admin_dashboard')
            elif perfil == "admin" and user_perfil == "admin":
                 return redirect('admin_dashboard')
            elif perfil == "operador" and user_perfil == "operador":
                 return redirect('admin_dashboard')
            elif perfil == "cliente" and not user.is_staff:
                return redirect('painel_dashboard')
            else:
                messages.error(request, "Tipo de usuário inválido para esse acesso.")
        else:
            messages.error(request, "Usuário/CPF ou senha inválidos.")
    return render(request, "accounts/login.html")


@login_required
def user_list(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
            usuarios = Cliente.objects.filter(perfil__in=["admin", "operador"]).select_related("empresa", "usuario")
    elif perfil == "admin":
        empresa = getattr(request.user.cliente_gestao, "empresa", None)
        if not empresa:
            return render(request, "sem_permissao.html")
        usuarios = Cliente.objects.filter(empresa=empresa, perfil__in=["admin", "operador"]).select_related("usuario", "empresa")
    else:
        return render(request, "sem_permissao.html")
    return render(request, "accounts/user_list.html", {"usuarios": usuarios})


@login_required
def user_create(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        allowed = [("admin", "Administrador")]
        empresa_queryset = Empresa.objects.all()
        empresa_initial = None
    elif perfil == "admin":
        allowed = [("operador", "Operador")]
        empresa_initial = getattr(request.user.cliente_gestao, "empresa", None)
        empresa_queryset = Empresa.objects.filter(id=empresa_initial.id) if empresa_initial else Empresa.objects.none()
    else:
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        form.fields['perfil'].choices = allowed
        form.fields['empresa'].queryset = empresa_queryset
        if empresa_initial:
            form.fields['empresa'].initial = empresa_initial
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("user_list")
    else:
        form = UsuarioForm()
        form.fields['perfil'].choices = allowed
        form.fields['empresa'].queryset = empresa_queryset
        if empresa_initial:
            form.fields['empresa'].initial = empresa_initial
    return render(request, "accounts/user_form.html", {"form": form})


def cliente_create(request):
    if request.method == "POST":
        form = ClientePublicoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cadastro realizado com sucesso.")
            return redirect("cliente_create")
    else:
        form = ClientePublicoForm()
    return render(request, "accounts/cliente_form.html", {"form": form})
