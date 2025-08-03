from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from gestao.models import Cliente
from .forms import UsuarioForm, ClientePublicoForm

def custom_login(request):
    if request.method == "POST":
        cpf = request.POST.get("cpf")
        password = request.POST.get("password")
        perfil = request.POST.get("perfil")

        user = None
        try:
            cliente = Cliente.objects.get(cpf=cpf)
            user = authenticate(
                request, username=cliente.usuario.username, password=password
            )
        except Cliente.DoesNotExist:
            user = None
        if user:
            login(request, user)
            if perfil in ["admin", "operador"] and user.is_staff:
                return redirect('/admin/')
            elif perfil == "cliente" and not user.is_staff:
                return redirect('/painel/')
            else:
                messages.error(request, "Tipo de usuário inválido para esse acesso.")
        else:
            messages.error(request, "CPF ou senha inválidos.")
    return render(request, "accounts/login.html")


@login_required
def user_list(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if not request.user.is_superuser and perfil != "admin":
        return render(request, "sem_permissao.html")
    usuarios = Cliente.objects.filter(criado_por=request.user)
    return render(request, "accounts/user_list.html", {"usuarios": usuarios})


@login_required
def user_create(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if not request.user.is_superuser and perfil != "admin":
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("user_list")
    else:
        form = UsuarioForm()
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

