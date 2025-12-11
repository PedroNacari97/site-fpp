from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.text import slugify
from gestao.models import Cliente
from .forms import UsuarioForm, ClientePublicoForm

def custom_login(request):
    if request.method == "POST":
        identifier = request.POST.get("identifier")
        password = request.POST.get("password")
        perfil = request.POST.get("perfil")

        username = None
        if perfil == "cliente":
            try:
                cliente = Cliente.objects.get(cpf=identifier)
                username = cliente.usuario.username
            except Cliente.DoesNotExist:
                username = None
        elif perfil == "superadmin":
            username = slugify(identifier)
        else:
            username = identifier

        user = authenticate(request, username=username, password=password)
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
        usuarios = Cliente.objects.filter(criado_por=request.user, perfil="admin")
    elif perfil == "admin":
        usuarios = Cliente.objects.filter(criado_por=request.user)
    else:
        return render(request, "sem_permissao.html")
    return render(request, "accounts/user_list.html", {"usuarios": usuarios})


@login_required
def user_create(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        allowed = [("admin", "Administrador")]
    elif perfil == "admin":
        allowed = [("operador", "Operador")]
    else:
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        form.fields['perfil'].choices = allowed
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("user_list")
    else:
        form = UsuarioForm()
        form.fields['perfil'].choices = allowed
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