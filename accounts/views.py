from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from gestao.models import Cliente, EmissorParceiro, Empresa
from gestao.utils import normalize_cpf, sync_cliente_activation

from .forms import ClientePublicoForm, UsuarioForm


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
                return redirect("admin_dashboard")
            if perfil == "admin" and user_perfil == "admin":
                return redirect("admin_dashboard")
            if perfil == "operador" and user_perfil == "operador":
                return redirect("admin_dashboard")
            if perfil == "cliente" and not user.is_staff:
                return redirect("painel_dashboard")
            if perfil == "parceiro" and EmissorParceiro.objects.filter(usuario=user, ativo=True).exists():
                return redirect("painel_parceiro_dashboard")
            messages.error(request, "Tipo de usuario invalido para esse acesso.")
        else:
            messages.error(request, "Usuario/CPF ou senha invalidos.")
    return render(request, "accounts/login.html")


def password_help(request):
    return render(request, "accounts/password_help.html")


def _get_user_scope(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        return {
            "perfil": perfil,
            "allowed_choices_create": [("admin", "Administrador")],
            "allowed_choices_edit": [("admin", "Administrador"), ("operador", "Operador")],
            "empresa_queryset": Empresa.objects.all(),
            "empresa_initial": None,
            "menu_ativo": "usuarios",
            "list_url_name": "user_list",
        }
    if perfil == "admin":
        empresa = getattr(request.user.cliente_gestao, "empresa", None)
        if not empresa:
            return None
        empresa_queryset = Empresa.objects.filter(id=empresa.id)
        return {
            "perfil": perfil,
            "allowed_choices_create": [("operador", "Operador")],
            "allowed_choices_edit": [("operador", "Operador")],
            "empresa_queryset": empresa_queryset,
            "empresa_initial": empresa,
            "menu_ativo": "operadores",
            "list_url_name": "operator_list",
        }
    return None


def _get_manageable_user_or_none(request, user_id):
    scope = _get_user_scope(request)
    if not scope:
        return None

    usuario = get_object_or_404(
        Cliente.objects.select_related("usuario", "empresa"),
        id=user_id,
        perfil__in=["admin", "operador"],
        ativo=True,
    )

    if request.user.is_superuser:
        return usuario

    empresa = scope["empresa_initial"]
    if (
        usuario.perfil == "operador"
        and empresa
        and usuario.empresa_id == empresa.id
    ):
        return usuario
    return None


@login_required
def user_list(request):
    scope = _get_user_scope(request)
    if not scope:
        return render(request, "sem_permissao.html")

    search_query = (request.GET.get("q") or "").strip()
    if request.user.is_superuser:
        usuarios_qs = Cliente.objects.filter(
            perfil__in=["admin", "operador"],
            ativo=True,
        ).select_related("empresa", "usuario")
    else:
        usuarios_qs = Cliente.objects.filter(
            empresa=scope["empresa_initial"],
            perfil__in=["admin", "operador"],
            ativo=True,
        ).select_related("empresa", "usuario")

    if search_query:
        normalized_search = normalize_cpf(search_query)
        search_filter = (
            Q(usuario__first_name__icontains=search_query)
            | Q(usuario__last_name__icontains=search_query)
            | Q(usuario__username__icontains=search_query)
            | Q(empresa__nome__icontains=search_query)
        )
        if normalized_search:
            search_filter |= Q(cpf__icontains=normalized_search)
        usuarios_qs = usuarios_qs.filter(search_filter)

    usuarios = []
    for usuario in usuarios_qs.order_by("perfil", "usuario__first_name", "usuario__username"):
        can_manage = False
        if request.user.is_superuser:
            can_manage = usuario.usuario_id != request.user.id
        else:
            can_manage = usuario.perfil == "operador" and usuario.usuario_id != request.user.id

        usuarios.append(
            {
                "usuario": usuario,
                "display_name": usuario.usuario.get_full_name()
                or usuario.usuario.first_name
                or usuario.usuario.username,
                "edit_url": reverse("user_edit", args=[usuario.id]) if can_manage else None,
                "delete_url": reverse("user_delete", args=[usuario.id]) if can_manage else None,
                "badge_class": "admin-users__tag--admin"
                if usuario.perfil == "admin"
                else "admin-users__tag--operador",
            }
        )

    return render(
        request,
        "accounts/user_list.html",
        {
            "usuarios": usuarios,
            "menu_ativo": "usuarios",
            "search_query": search_query,
        },
    )


@login_required
def operator_list(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if request.user.is_superuser:
        operadores = Cliente.objects.filter(perfil="operador").select_related("empresa", "usuario")
    elif perfil == "admin":
        empresa = getattr(request.user.cliente_gestao, "empresa", None)
        if not empresa:
            return render(request, "sem_permissao.html")
        operadores = Cliente.objects.filter(empresa=empresa, perfil="operador").select_related("usuario", "empresa")
    else:
        return render(request, "sem_permissao.html")

    if "toggle" in request.GET and request.method == "GET":
        operador = get_object_or_404(operadores, id=request.GET["toggle"])
        operador.ativo = not operador.ativo
        operador.save(update_fields=["ativo"])
        sync_cliente_activation(operador)
        messages.success(
            request,
            f"Operador {'ativado' if operador.ativo else 'desativado'} com sucesso."
        )
        return redirect("operator_list")

    return render(
        request,
        "accounts/operator_list.html",
        {"usuarios": operadores, "menu_ativo": "operadores"},
    )


@login_required
def user_create(request):
    scope = _get_user_scope(request)
    if not scope:
        return render(request, "sem_permissao.html")

    if request.method == "POST":
        form = UsuarioForm(request.POST)
        form.fields["perfil"].choices = scope["allowed_choices_create"]
        form.fields["empresa"].queryset = scope["empresa_queryset"]
        if scope["empresa_initial"]:
            form.fields["empresa"].initial = scope["empresa_initial"]
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuario criado com sucesso.")
            return redirect(scope["list_url_name"])
    else:
        form = UsuarioForm()
        form.fields["perfil"].choices = scope["allowed_choices_create"]
        form.fields["empresa"].queryset = scope["empresa_queryset"]
        if scope["empresa_initial"]:
            form.fields["empresa"].initial = scope["empresa_initial"]

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "menu_ativo": scope["menu_ativo"],
            "form_title": "Novo Usuario",
            "form_subtitle": "Estrutura de formulario unificada para administradores e operadores.",
            "submit_label": "Salvar",
            "list_url": reverse(scope["list_url_name"]),
        },
    )


@login_required
def user_edit(request, user_id):
    scope = _get_user_scope(request)
    if not scope:
        return render(request, "sem_permissao.html")

    usuario = _get_manageable_user_or_none(request, user_id)
    if not usuario:
        return render(request, "sem_permissao.html")

    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=usuario)
        form.fields["perfil"].choices = scope["allowed_choices_edit"]
        form.fields["empresa"].queryset = scope["empresa_queryset"]
        if scope["empresa_initial"]:
            form.fields["empresa"].initial = scope["empresa_initial"]
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuario atualizado com sucesso.")
            return redirect(scope["list_url_name"])
    else:
        form = UsuarioForm(instance=usuario)
        form.fields["perfil"].choices = scope["allowed_choices_edit"]
        form.fields["empresa"].queryset = scope["empresa_queryset"]
        if scope["empresa_initial"]:
            form.fields["empresa"].initial = scope["empresa_initial"]

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "menu_ativo": scope["menu_ativo"],
            "form_title": "Editar Usuario",
            "form_subtitle": "Atualize os dados e mantenha o acesso alinhado com a operacao.",
            "submit_label": "Salvar alteracoes",
            "list_url": reverse(scope["list_url_name"]),
        },
    )


@login_required
def user_delete(request, user_id):
    scope = _get_user_scope(request)
    if not scope:
        return render(request, "sem_permissao.html")

    usuario = _get_manageable_user_or_none(request, user_id)
    if not usuario:
        return render(request, "sem_permissao.html")

    if usuario.usuario_id == request.user.id:
        messages.error(request, "Nao e permitido remover o proprio acesso.")
        return redirect(scope["list_url_name"])

    if request.method == "POST":
        usuario.ativo = False
        usuario.save(update_fields=["ativo"])
        usuario.usuario.is_active = False
        usuario.usuario.is_staff = False
        usuario.usuario.save(update_fields=["is_active", "is_staff"])
        messages.success(request, "Usuario removido com sucesso.")
        return redirect(scope["list_url_name"])

    return render(
        request,
        "accounts/user_confirm_delete.html",
        {
            "usuario": usuario,
            "menu_ativo": scope["menu_ativo"],
            "list_url": reverse(scope["list_url_name"]),
        },
    )


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
