from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.sessions.models import Session
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from gestao.models import Cliente, EmissorParceiro, Empresa
from gestao.utils import normalize_cpf, sync_cliente_activation

from .access import get_user_operational_role
from .forms import ClientePublicoForm, UsuarioForm
from .security import (
    format_lockout_message,
    get_client_ip,
    get_pending_superadmin_mfa,
    is_login_allowed,
    is_security_action_allowed,
    log_security_event,
    register_login_failure,
    register_security_action_attempt,
    reset_login_failures,
    start_superadmin_mfa_challenge,
    verify_superadmin_mfa_code,
)
from .models import ActiveUserSession


_LOGIN_ERROR_MSG = "CPF e/ou senha invalidos. Tente novamente."
_RESET_GENERIC_MSG = (
    "Se o CPF estiver cadastrado com um email valido, voce recebera as instrucoes em instantes."
)


def verify_turnstile_token(token, remote_ip):
    """Valida token do Cloudflare Turnstile. Sem chave configurada, nao bloqueia."""
    if not settings.TURNSTILE_SECRET_KEY:
        return True
    if not token:
        return False
    try:
        import requests as req_lib
        resp = req_lib.post(
            settings.TURNSTILE_API_URL,
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
                "remoteip": remote_ip,
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False)
    except Exception:
        return bool(getattr(settings, "TURNSTILE_FAIL_OPEN", False))


def _validate_turnstile_or_message(request, *, identifier="", scope="default"):
    turnstile_token = request.POST.get("cf-turnstile-response", "")
    if verify_turnstile_token(turnstile_token, get_client_ip(request)):
        return True
    log_security_event(
        "turnstile_failed",
        request=request,
        identifier=identifier,
        details={"scope": scope},
    )
    messages.error(request, "Verificacao de seguranca falhou. Tente novamente.")
    return False


def _reset_timeout_label():
    total_seconds = int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 0) or 0)
    total_minutes = max(1, total_seconds // 60)
    if total_minutes >= 120 and total_minutes % 60 == 0:
        return f"{total_minutes // 60} horas"
    if total_minutes >= 60:
        hours = total_minutes // 60
        minutes = total_minutes % 60
        suffix = f" e {minutes} minuto(s)" if minutes else ""
        return f"{hours} hora(s){suffix}"
    return f"{total_minutes} minuto(s)"


def _invalidate_user_sessions(user):
    user_id = str(user.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            if session.get_decoded().get("_auth_user_id") == user_id:
                session.delete()
        except Exception:
            continue
    ActiveUserSession.objects.filter(user=user).delete()


def _build_login_context(mode="default", **extra):
    is_superadmin = mode == "superadmin"
    context = {
        "login_mode": mode,
        "login_title": "Acesso Super Admin" if is_superadmin else "Acesso ao painel",
        "login_subtitle": "Entre com seu usuario de superadmin para acessar a camada global."
        if is_superadmin
        else "Use suas credenciais para continuar.",
        "identifier_label": "Usuario" if is_superadmin else "CPF",
        "identifier_placeholder": "Digite seu usuario" if is_superadmin else "Digite seu CPF",
        "show_access_select": not is_superadmin,
        "show_register": not is_superadmin,
        "alternate_login_url": reverse("login_custom") if is_superadmin else reverse("superadmin_login"),
        "alternate_login_label": "Voltar para o login comum" if is_superadmin else "Acesso Super Admin",
        "entered_identifier": "",
        "selected_profile": "cliente",
        "mfa_pending": False,
        "mfa_masked_email": "",
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", "") or "",
    }
    context.update(extra)
    return context


def _resolve_login_destination(user, perfil):
    user_perfil = get_user_operational_role(user)
    if perfil == "admin" and user_perfil == "admin":
        return "admin_dashboard"
    if perfil == "operador" and user_perfil == "operador":
        return "admin_dashboard"
    if perfil == "cliente" and not user.is_staff and not user.is_superuser:
        return "painel_dashboard"
    if perfil == "parceiro" and EmissorParceiro.objects.filter(usuario=user, ativo=True).exists():
        return "painel_parceiro_dashboard"
    return None


def _build_pending_superadmin_context(request):
    challenge = get_pending_superadmin_mfa(request)
    if not challenge:
        return _build_login_context("superadmin")

    return _build_login_context(
        "superadmin",
        login_subtitle="Digite o codigo de verificacao enviado para concluir o acesso.",
        mfa_pending=True,
        mfa_masked_email=challenge.get("masked_email", ""),
        entered_identifier=challenge.get("identifier", ""),
    )


def custom_login(request):
    perfil = request.POST.get("perfil") or "cliente"
    identifier = request.POST.get("identifier") or ""

    if request.method == "POST":
        password = request.POST.get("password")
        lock_scope = f"default:{perfil}"

        login_allowed, remaining_seconds = is_login_allowed(request, identifier, lock_scope)
        if not login_allowed:
            messages.error(request, format_lockout_message(remaining_seconds))
            return render(
                request,
                "accounts/login.html",
                _build_login_context(
                    entered_identifier=identifier,
                    selected_profile=perfil,
                ),
            )

        if not _validate_turnstile_or_message(request, identifier=identifier, scope=lock_scope):
            return render(
                request,
                "accounts/login.html",
                _build_login_context(
                    entered_identifier=identifier,
                    selected_profile=perfil,
                ),
            )

        cpf = normalize_cpf(identifier)
        user = authenticate(request, cpf=cpf, password=password)
        if user:
            destination = _resolve_login_destination(user, perfil)
            if destination:
                reset_login_failures(request, identifier, lock_scope)
                log_security_event(
                    "login_success",
                    request=request,
                    user=user,
                    identifier=cpf or identifier,
                    details={"scope": lock_scope},
                )
                login(request, user)
                return redirect(destination)
            log_security_event(
                "login_denied_profile",
                request=request,
                user=user,
                identifier=cpf or identifier,
                details={"requested_profile": perfil},
            )
            messages.error(request, "Tipo de usuario invalido para esse acesso.")
        else:
            register_login_failure(request, identifier, lock_scope)
            messages.error(request, _LOGIN_ERROR_MSG)
    return render(
        request,
        "accounts/login.html",
        _build_login_context(
            entered_identifier=identifier,
            selected_profile=perfil,
        ),
    )


def superadmin_login(request):
    if request.method == "GET" and request.GET.get("reset_mfa") == "1":
        request.session.pop("superadmin_mfa_pending", None)
        request.session.modified = True

    if request.method == "POST" and request.POST.get("action") == "verify_mfa":
        user, error_message = verify_superadmin_mfa_code(
            request, request.POST.get("mfa_code")
        )
        if user:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("admin_dashboard")
        messages.error(request, error_message)
        return render(request, "accounts/login.html", _build_pending_superadmin_context(request))

    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password")
        login_allowed, remaining_seconds = is_login_allowed(request, identifier, "superadmin")
        if not login_allowed:
            messages.error(request, format_lockout_message(remaining_seconds))
            return render(
                request,
                "accounts/login.html",
                _build_login_context("superadmin", entered_identifier=identifier),
            )

        if not _validate_turnstile_or_message(request, identifier=identifier, scope="superadmin"):
            return render(
                request,
                "accounts/login.html",
                _build_login_context("superadmin", entered_identifier=identifier),
            )

        user = authenticate(request, username=identifier, password=password)
        if user and user.is_superuser:
            reset_login_failures(request, identifier, "superadmin")
            if not settings.SUPERADMIN_MFA_ENABLED:
                log_security_event(
                    "login_success",
                    request=request,
                    user=user,
                    identifier=identifier,
                    details={"scope": "superadmin"},
                )
                login(request, user)
                return redirect("admin_dashboard")
            challenge_started, error_message = start_superadmin_mfa_challenge(
                request, user, identifier
            )
            if challenge_started:
                messages.success(
                    request,
                    "Enviamos um codigo de verificacao para o email cadastrado do superadmin.",
                )
                return render(
                    request,
                    "accounts/login.html",
                    _build_pending_superadmin_context(request),
                )
            messages.error(request, error_message)
        else:
            register_login_failure(request, identifier, "superadmin")
            messages.error(request, "Usuario ou senha invalidos para o acesso de superadmin.")
        return render(
            request,
            "accounts/login.html",
            _build_login_context("superadmin", entered_identifier=identifier),
        )
    return render(
        request,
        "accounts/login.html",
        _build_pending_superadmin_context(request),
    )


def password_help(request):
    return render(request, "accounts/password_help.html")


def password_reset_request(request):
    """Formulario de solicitacao de reset de senha via CPF."""
    context = {
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", "") or "",
    }

    if request.method == "POST":
        cpf_raw = request.POST.get("cpf", "")
        cpf = normalize_cpf(cpf_raw)
        reset_identifier = cpf or cpf_raw.strip() or "<vazio>"

        reset_allowed, remaining_seconds = is_security_action_allowed(
            request, reset_identifier, "password_reset"
        )
        if not reset_allowed:
            messages.error(
                request,
                "Muitas solicitacoes de redefinicao. Aguarde "
                f"{max(1, (remaining_seconds + 59) // 60)} minuto(s) antes de tentar novamente.",
            )
            return render(request, "accounts/password_reset_request.html", context)

        if not _validate_turnstile_or_message(
            request, identifier=reset_identifier, scope="password_reset"
        ):
            return render(request, "accounts/password_reset_request.html", context)

        register_security_action_attempt(
            request,
            reset_identifier,
            "password_reset",
            limit=settings.SECURITY_PASSWORD_RESET_LIMIT,
            lockout_minutes=settings.SECURITY_PASSWORD_RESET_LOCKOUT_MINUTES,
            event_prefix="password_reset_request",
        )

        if cpf:
            try:
                cliente = Cliente.objects.select_related("usuario").get(cpf=cpf, ativo=True)
                user = cliente.usuario
                if user.email and user.is_active:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    reset_link = request.build_absolute_uri(
                        reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
                    )
                    send_mail(
                        subject="Redefinicao de senha - NC Fly",
                        message=(
                            f"Ola,\n\n"
                            f"Recebemos uma solicitacao de redefinicao de senha para a sua conta NC Fly.\n\n"
                            f"Clique no link abaixo para criar uma nova senha (valido por ate {_reset_timeout_label()}):\n\n"
                            f"{reset_link}\n\n"
                            f"Se voce nao solicitou isso, ignore este email.\n\n"
                            f"Equipe NC Fly"
                        ),
                        from_email=settings.PASSWORD_RESET_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                    log_security_event(
                        "password_reset_email_sent",
                        request=request,
                        user=user,
                        identifier=cpf,
                    )
            except Cliente.DoesNotExist:
                log_security_event(
                    "password_reset_unknown_identifier",
                    request=request,
                    identifier=reset_identifier,
                )

        messages.success(request, _RESET_GENERIC_MSG)
        return redirect("password_reset_request")

    return render(request, "accounts/password_reset_request.html", context)


def password_reset_confirm(request, uidb64, token):
    """Formulario para definir nova senha via link de reset."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    invalid_context = {"token_invalid": True}

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        log_security_event(
            "password_reset_invalid_token",
            request=request,
            identifier=uidb64,
            details={"reason": "user_decode_failed"},
        )
        return render(request, "accounts/password_reset_confirm.html", invalid_context)

    if not user.is_active:
        log_security_event(
            "password_reset_inactive_user",
            request=request,
            user=user,
            identifier=str(user.pk),
            details={"reason": "user_inactive"},
        )
        return render(request, "accounts/password_reset_confirm.html", invalid_context)

    if not default_token_generator.check_token(user, token):
        log_security_event(
            "password_reset_invalid_token",
            request=request,
            user=user,
            identifier=str(user.pk),
            details={"reason": "token_check_failed"},
        )
        return render(request, "accounts/password_reset_confirm.html", invalid_context)

    if request.method == "POST":
        nova_senha = request.POST.get("nova_senha", "")
        confirmar_senha = request.POST.get("confirmar_senha", "")

        try:
            validate_password(nova_senha, user=user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return render(
                request,
                "accounts/password_reset_confirm.html",
                {"uidb64": uidb64, "token": token},
            )

        if nova_senha != confirmar_senha:
            messages.error(request, "As senhas nao coincidem.")
            return render(
                request,
                "accounts/password_reset_confirm.html",
                {"uidb64": uidb64, "token": token},
            )

        user.set_password(nova_senha)
        user.save(update_fields=["password"])
        _invalidate_user_sessions(user)
        log_security_event("password_reset_completed", request=request, user=user)
        messages.success(request, "Senha redefinida com sucesso. Faca login com a nova senha.")
        return redirect("login_custom")

    return render(
        request,
        "accounts/password_reset_confirm.html",
        {"uidb64": uidb64, "token": token},
    )


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


def _build_users_queryset(request, scope):
    if request.user.is_superuser:
        return Cliente.objects.filter(
            perfil__in=["admin", "operador"],
            ativo=True,
        ).select_related("empresa", "usuario")
    return Cliente.objects.filter(
        empresa=scope["empresa_initial"],
        perfil__in=["admin", "operador"],
        ativo=True,
    ).select_related("empresa", "usuario")


def _configure_usuario_form(form, scope, *, create=False):
    form.fields["perfil"].choices = (
        scope["allowed_choices_create"] if create else scope["allowed_choices_edit"]
    )
    form.fields["empresa"].queryset = scope["empresa_queryset"]
    if scope["empresa_initial"]:
        form.fields["empresa"].initial = scope["empresa_initial"]
    return form


def _render_user_form(request, scope, form, *, form_title, form_subtitle, submit_label):
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "menu_ativo": scope["menu_ativo"],
            "form_title": form_title,
            "form_subtitle": form_subtitle,
            "submit_label": submit_label,
            "list_url": reverse(scope["list_url_name"]),
        },
    )


@login_required
def user_list(request):
    scope = _get_user_scope(request)
    if not scope:
        return render(request, "sem_permissao.html")

    search_query = (request.GET.get("q") or "").strip()
    usuarios_qs = _build_users_queryset(request, scope)

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
    empresas_ids = set()
    for usuario in usuarios_qs.order_by("perfil", "usuario__first_name", "usuario__username"):
        if usuario.empresa_id:
            empresas_ids.add(usuario.empresa_id)
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
            "totais": {
                "usuarios": len(usuarios),
                "admins": sum(1 for row in usuarios if row["usuario"].perfil == "admin"),
                "operadores": sum(1 for row in usuarios if row["usuario"].perfil == "operador"),
                "empresas": len(empresas_ids),
            },
            "is_superadmin": request.user.is_superuser,
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
        if not operador.ativo and operador.empresa and operador.empresa.limite_colaboradores_atingido():
            messages.error(
                request,
                f"O limite de {operador.empresa.limite_colaboradores} colaboradores para esta empresa foi atingido.",
            )
            return redirect("operator_list")
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
        form = _configure_usuario_form(UsuarioForm(request.POST), scope, create=True)
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuario criado com sucesso.")
            return redirect(scope["list_url_name"])
    else:
        form = _configure_usuario_form(UsuarioForm(), scope, create=True)

    return _render_user_form(
        request,
        scope,
        form,
        form_title="Novo Usuario",
        form_subtitle="Estrutura de formulario unificada para administradores e operadores.",
        submit_label="Salvar",
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
        form = _configure_usuario_form(
            UsuarioForm(request.POST, instance=usuario),
            scope,
            create=False,
        )
        if form.is_valid():
            form.save(criado_por=request.user)
            messages.success(request, "Usuario atualizado com sucesso.")
            return redirect(scope["list_url_name"])
    else:
        form = _configure_usuario_form(UsuarioForm(instance=usuario), scope, create=False)

    return _render_user_form(
        request,
        scope,
        form,
        form_title="Editar Usuario",
        form_subtitle="Atualize os dados e mantenha o acesso alinhado com a operacao.",
        submit_label="Salvar alteracoes",
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
