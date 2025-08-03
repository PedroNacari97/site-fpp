from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from gestao.models import Cliente
from .forms import UsuarioForm, ClientePublicoForm, LoginForm


class UserLoginView(FormView):
    """Handle authentication for clients, admins and operators."""

    template_name = "accounts/login.html"
    form_class = LoginForm

    def form_valid(self, form):
        identifier = form.cleaned_data["identifier"]
        password = form.cleaned_data["password"]
        access_type = self.request.POST.get("access_type")

        username = identifier
        if access_type == "cliente":
            cliente = Cliente.objects.filter(cpf=identifier).first()
            if cliente:
                username = cliente.usuario.username

        user = authenticate(self.request, username=username, password=password)
        if user:
            perfil = getattr(getattr(user, "cliente_gestao", None), "perfil", "")
            if access_type == "admin" and user.is_staff and perfil == "admin":
                login(self.request, user)
                return redirect("admin_dashboard")
            if access_type == "operador" and user.is_staff and perfil == "operador":
                login(self.request, user)
                return redirect("admin_dashboard")
            if access_type == "cliente" and not user.is_staff:
                cliente_obj = Cliente.objects.filter(usuario=user).first()
                if cliente_obj and not cliente_obj.ativo:
                    messages.error(self.request, "Sua conta está inativa. Entre em contato com o administrador.")
                else:
                    login(self.request, user)
                    return redirect("painel_dashboard")
        messages.error(self.request, "Credenciais inválidas ou sem permissão.")
        return self.form_invalid(form)


@login_required
def list_users(request):
    user_role = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        usuarios = Cliente.objects.filter(criado_por=request.user, perfil="admin")
    elif user_role == "admin":
        usuarios = Cliente.objects.filter(criado_por=request.user)
    else:
        return render(request, "sem_permissao.html")
    return render(request, "accounts/user_list.html", {"usuarios": usuarios})


@login_required
def create_user(request):
    user_role = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        allowed = [("admin", "Administrador")]
    elif user_role == "admin":
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


def register_client(request):
    if request.method == "POST":
        form = ClientePublicoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cadastro realizado com sucesso.")
            return redirect("cliente_create")
    else:
        form = ClientePublicoForm()
    return render(request, "accounts/cliente_form.html", {"form": form})