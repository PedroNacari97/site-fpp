from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
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
                return redirect('/superadmin/empresas/')
            elif perfil == "admin" and user_perfil == "admin":
                return redirect('/admin/')
            elif perfil == "operador" and user_perfil == "operador":
                return redirect('/admin/')
            elif perfil == "cliente" and not user.is_staff:
                return redirect('/painel/')
            else:
                messages.error(request, "Tipo de usuário inválido para esse acesso.")
        else:
            messages.error(request, "Usuário/CPF ou senha inválidos.")
    return render(request, "accounts/login.html")


@login_required
def user_list(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.user.is_superuser:
        usuarios = Cliente.objects.filter(criado_por=request.user, perfil="admin")
    elif perfil == "admin" and empresa:
        usuarios = Cliente.objects.filter(empresa=empresa, perfil__in=["admin", "operador"])
    else:
        return render(request, "sem_permissao.html")
    return render(request, "accounts/user_list.html", {"usuarios": usuarios})


@login_required
def user_create(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.user.is_superuser:
        allowed = [("admin", "Administrador")]
    elif perfil == "admin" and empresa:
        allowed = [("operador", "Operador")]
    else:
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = UsuarioForm(request.POST)
        form.fields['perfil'].choices = allowed
        if form.is_valid():
            perfil_novo = form.cleaned_data['perfil']
            if empresa:
                limites = {
                    'admin': empresa.limite_administradores,
                    'operador': empresa.limite_operadores,
                }
                total = Cliente.objects.filter(empresa=empresa, perfil=perfil_novo).count()
                if total >= limites.get(perfil_novo, 0):
                    messages.error(request, "Limite de usuários atingido.")
                    return render(request, "accounts/user_form.html", {"form": form})
            form.save(criado_por=request.user, empresa=empresa)
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("user_list")
    else:
        form = UsuarioForm()
        form.fields['perfil'].choices = allowed
    return render(request, "accounts/user_form.html", {"form": form})


@login_required
def user_delete(request, user_id):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if perfil != "admin" or not empresa:
        return render(request, "sem_permissao.html")
    usuario = get_object_or_404(Cliente, id=user_id, empresa=empresa, perfil__in=["admin", "operador"])
    usuario.usuario.delete()
    usuario.delete()
    messages.success(request, "Usuário removido com sucesso.")
    return redirect("user_list")


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