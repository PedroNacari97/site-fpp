"""Views de autenticacao do Portal B2C (login, cadastro, OAuth, unsubscribe).

Isoladas das views do SaaS B2B (`accounts/`) — usam `PortalUser` e sessao
propria (`PORTAL_SESSION_USER_KEY`).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, send_mail
from html import escape as html_escape
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.security import (
    format_lockout_message,
    get_client_ip,
    get_request_url,
    get_user_agent,
    log_security_event,
)

from .auth import (
    GoogleOAuthError,
    LOGIN_SCOPE,
    PORTAL_SESSION_NEXT_KEY,
    authenticate_email_user,
    build_google_authorize_url,
    check_login_allowed,
    check_register_allowed,
    exchange_code_for_user,
    google_oauth_configured,
    is_safe_next,
    login_portal_user,
    logout_portal_user,
    get_portal_user,
    normalize_email,
    register_email_user,
    register_register_attempt,
)
from .models import (
    OptInAlertaPassagem,
    OptInArtigoNovo,
    PortalUser,
    _documento_hash,
    criar_opt_ins_no_cadastro,
)
from .services.preuser import link_pre_user_to


PORTAL_B2C_TERMOS_VERSAO = getattr(settings, "PORTAL_B2C_TERMOS_VERSAO", "2026-04")


def _safe_next(request) -> str:
    nxt = request.GET.get("next") or request.POST.get("next") or ""
    return nxt if is_safe_next(nxt) else ""


def _render_auth(request, template, context=None):
    ctx = {
        "next_url": _safe_next(request),
        "google_oauth_enabled": google_oauth_configured(),
        "google_login_url": reverse("portal_google_login"),
        "portal_terms_version": PORTAL_B2C_TERMOS_VERSAO,
        "portal_terms_url": reverse("portal_termos"),
        "portal_privacy_url": reverse("portal_privacidade"),
    }
    if context:
        ctx.update(context)
    return render(request, template, ctx)


def _welcome_logo_url() -> str:
    logo_path = str(getattr(settings, "PORTAL_SITE_LOGO_URL", "") or "").strip()
    if not logo_path:
        return ""
    if logo_path.startswith("http://") or logo_path.startswith("https://"):
        return logo_path
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        base_url = "http://localhost:8000"
    return f"{base_url}{logo_path}"


def _build_welcome_email_bodies(user: PortalUser, termos_url: str, privacidade_url: str, home_url: str, artigos_url: str, alertas_url: str) -> tuple[str, str]:
    """Gera versao texto + HTML do email de boas-vindas do Portal B2C."""
    first_name = (user.nome or "").strip().split()[0] if (user.nome or "").strip() else "viajante"

    text_lines = [
        f"Olá, {first_name}!",
        "",
        "Seu cadastro no NC Fly foi confirmado.",
        "",
        "A partir de agora você tem acesso a:",
        "  - Todos os artigos de estudo (passagens, milhas, roteiros)",
        "  - Alertas de passagens com desconto por e-mail",
        "  - Avisos quando publicarmos um artigo novo",
        "",
        f"Começar agora: {home_url}",
        f"Ver artigos: {artigos_url}",
        f"Alertas de passagens: {alertas_url}",
        "",
        "Você decide cada canal de e-mail separadamente. Todo e-mail que",
        "enviamos tem o link de cancelamento daquele canal específico.",
        "",
        f"Termos aceitos no cadastro (versão {PORTAL_B2C_TERMOS_VERSAO}):",
        f"  Termos de uso: {termos_url}",
        f"  Privacidade:   {privacidade_url}",
        "",
        "Boas viagens,",
        "Equipe NC Fly",
    ]
    text = "\n".join(text_lines)

    logo_url = _welcome_logo_url()
    logo_block = ""
    if logo_url:
        logo_block = (
            f'<div style="margin:0 0 18px;"><img src="{html_escape(logo_url)}" '
            f'alt="NC Fly" width="120" style="display:block;max-width:120px;height:auto;"></div>'
        )

    html = f"""
    <html>
      <body style="margin:0;padding:24px;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
        <div style="max-width:640px;margin:0 auto;padding:32px 28px;border-radius:28px;background:#ffffff;">
          {logo_block}
          <div style="margin:0 0 8px;font-size:12px;font-weight:800;letter-spacing:0.12em;color:#ff7a00;text-transform:uppercase;">Cadastro confirmado</div>
          <h1 style="margin:0 0 12px;font-size:30px;line-height:1.15;color:#13294b;">Bem-vindo, {html_escape(first_name)}.</h1>
          <p style="margin:0 0 20px;font-size:16px;line-height:1.7;color:#42526b;">
            Seu acesso ao NC Fly está pronto. Abre o primeiro artigo e deixa o e-mail cadastrado para os alertas. A gente avisa quando sair passagem boa.
          </p>

          <div style="margin:0 0 18px;padding:18px 18px 14px;border:1px solid #f1d8ca;border-radius:18px;background:#fff8f3;">
            <div style="margin:0 0 8px;font-size:13px;font-weight:800;color:#ff7a00;text-transform:uppercase;letter-spacing:0.06em;">O que já está liberado</div>
            <ul style="margin:0;padding:0 0 0 18px;font-size:15px;line-height:1.8;color:#13294b;">
              <li>Todos os artigos de estudo (passagens, milhas, roteiros)</li>
              <li>Alertas de passagens com desconto por e-mail</li>
              <li>Avisos quando publicarmos um artigo novo</li>
            </ul>
          </div>

          <div style="margin:0 0 22px;">
            <a href="{html_escape(artigos_url)}" style="display:inline-block;margin:0 8px 8px 0;padding:12px 18px;border-radius:999px;background:#13294b;color:#ffffff;text-decoration:none;font-size:14px;font-weight:800;">
              Ver artigos de estudo
            </a>
            <a href="{html_escape(alertas_url)}" style="display:inline-block;margin:0 0 8px 0;padding:12px 18px;border-radius:999px;background:#fff0e6;color:#ff7a00;text-decoration:none;font-size:14px;font-weight:800;">
              Ver alertas ativos
            </a>
          </div>

          <div style="padding-top:14px;border-top:1px solid #e2e8f0;font-size:12px;line-height:1.7;color:#64748b;">
            Termos aceitos no cadastro (versão {html_escape(PORTAL_B2C_TERMOS_VERSAO)}):<br>
            <a href="{html_escape(termos_url)}" style="color:#2f6fd6;text-decoration:underline;">Termos de uso</a>
            &nbsp;·&nbsp;
            <a href="{html_escape(privacidade_url)}" style="color:#2f6fd6;text-decoration:underline;">Política de privacidade</a>
          </div>
        </div>
      </body>
    </html>
    """
    return text, html


def _send_confirmation_email(user: PortalUser, request) -> None:
    """Envia email de confirmacao de cadastro com links dos termos aceitos."""
    try:
        termos_url = request.build_absolute_uri(reverse("portal_termos"))
        privacidade_url = request.build_absolute_uri(reverse("portal_privacidade"))
        home_url = request.build_absolute_uri(reverse("portal_home"))
        artigos_url = request.build_absolute_uri(reverse("portal_artigos"))
        alertas_url = request.build_absolute_uri(reverse("portal_alertas"))

        text_body, html_body = _build_welcome_email_bodies(
            user,
            termos_url=termos_url,
            privacidade_url=privacidade_url,
            home_url=home_url,
            artigos_url=artigos_url,
            alertas_url=alertas_url,
        )
        from_email = getattr(settings, "SUPPORT_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)
        reply_to = getattr(settings, "PORTAL_CONTACT_EMAIL", "") or from_email

        message = EmailMultiAlternatives(
            subject="Bem-vindo ao NC Fly, cadastro confirmado",
            body=text_body,
            from_email=from_email,
            to=[user.email],
            reply_to=[reply_to] if reply_to else None,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=True)
    except Exception:
        # Nunca quebrar o cadastro por falha no envio transacional
        pass


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def portal_login(request):
    """Login do Portal B2C por email + senha."""
    if get_portal_user(request):
        return redirect(_safe_next(request) or reverse("portal_home"))

    if request.method == "GET":
        return _render_auth(request, "portal/auth/login.html")

    email = normalize_email(request.POST.get("email"))
    senha = request.POST.get("senha") or ""

    allowed, remaining = check_login_allowed(request, email)
    if not allowed:
        messages.error(request, format_lockout_message(remaining))
        return _render_auth(request, "portal/auth/login.html", {"entered_email": email})

    user = authenticate_email_user(request=request, email=email, senha=senha)
    if user is None:
        messages.error(request, "Email ou senha invalidos. Tente novamente.")
        return _render_auth(request, "portal/auth/login.html", {"entered_email": email})

    login_portal_user(request, user)
    link_pre_user_to(user, request)
    log_security_event(
        "portal_b2c_login_success",
        request=request,
        identifier=email,
        details={"user_id": user.pk},
    )
    destination = _safe_next(request) or reverse("portal_home")
    return redirect(destination)


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def portal_register(request):
    """Cadastro do Portal B2C."""
    if get_portal_user(request):
        return redirect(_safe_next(request) or reverse("portal_home"))

    if request.method == "GET":
        return _render_auth(request, "portal/auth/register.html")

    email = normalize_email(request.POST.get("email"))
    nome = (request.POST.get("nome") or "").strip()
    senha = request.POST.get("senha") or ""
    confirmar = request.POST.get("confirmar_senha") or ""
    aceite = request.POST.get("aceite_termos") == "on"

    # 1. aceite obrigatorio — bloqueia se nao marcou
    if not aceite:
        messages.error(
            request,
            "Para continuar voce precisa ler e aceitar os Termos de Uso e a Politica de Privacidade.",
        )
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )

    # 2. rate limit de cadastro
    allowed, remaining = check_register_allowed(request, email)
    if not allowed:
        messages.error(request, format_lockout_message(remaining))
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )

    # 3. validacao basica
    if "@" not in email:
        messages.error(request, "Informe um email valido.")
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )
    if senha != confirmar:
        messages.error(request, "As senhas nao coincidem.")
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )
    try:
        validate_password(senha)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )

    register_register_attempt(request, email)

    # 4. cria usuario
    try:
        user = register_email_user(
            request=request,
            email=email,
            nome=nome,
            senha=senha,
        )
    except ValueError:
        # email ja existe — resposta generica pra nao vazar enumeracao
        messages.error(
            request,
            "Nao foi possivel concluir o cadastro. Caso ja tenha conta, use 'Entrar'.",
        )
        log_security_event(
            "portal_b2c_register_duplicate_email",
            request=request,
            identifier=email,
        )
        return _render_auth(
            request,
            "portal/auth/register.html",
            {"entered_email": email, "entered_nome": nome},
        )

    # 5. grava opt-ins (alertas + artigos) — tabelas separadas
    # Hash do "documento" aceito — texto sintetico do consentimento
    consentimento_texto = (
        f"termos-v{PORTAL_B2C_TERMOS_VERSAO}|privacidade-v{PORTAL_B2C_TERMOS_VERSAO}|"
        f"optin-alerta-passagem|optin-artigo-novo"
    )
    hash_consentimento = _documento_hash(consentimento_texto)
    criar_opt_ins_no_cadastro(
        user,
        ip=get_client_ip(request),
        user_agent=get_user_agent(request),
        versao_termos=PORTAL_B2C_TERMOS_VERSAO,
        hash_termos=hash_consentimento,
        url_origem=get_request_url(request),
    )

    # 6. confirma email (infra existente — best-effort, nao bloqueia)
    _send_confirmation_email(user, request)

    # 6.1 notifica admin sobre novo cadastro (best-effort)
    try:
        from portal.services.admin_notifications import enviar_email_admin_novo_cadastro
        enviar_email_admin_novo_cadastro(user, via="email")
    except Exception:  # noqa: BLE001
        pass

    # 7. loga
    login_portal_user(request, user)
    link_pre_user_to(user, request)
    messages.success(
        request,
        "Cadastro concluido! Enviamos um email de confirmacao com os termos aceitos.",
    )
    destination = _safe_next(request) or reverse("portal_home")
    return redirect(destination)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def portal_logout(request):
    user = get_portal_user(request)
    if user:
        log_security_event(
            "portal_b2c_logout",
            request=request,
            identifier=user.email,
            details={"user_id": user.pk},
        )
    logout_portal_user(request)
    messages.info(request, "Sessao encerrada.")
    return redirect("portal_home")


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def portal_google_login(request):
    """Redireciona para a tela de consentimento do Google."""
    if not google_oauth_configured():
        messages.error(
            request,
            "Login com Google temporariamente indisponivel. Use email e senha.",
        )
        return redirect("portal_login")
    try:
        auth_url = build_google_authorize_url(request, next_url=_safe_next(request))
    except GoogleOAuthError:
        messages.error(request, "Nao foi possivel iniciar o login com Google.")
        return redirect("portal_login")
    return HttpResponseRedirect(auth_url)


@require_http_methods(["GET"])
def portal_google_callback(request):
    code = request.GET.get("code") or ""
    state = request.GET.get("state") or ""
    error = request.GET.get("error") or ""

    if error:
        log_security_event(
            "portal_b2c_google_error",
            request=request,
            details={"error": error[:100]},
        )
        messages.error(request, "Login com Google cancelado ou negado.")
        return redirect("portal_login")

    if not code or not state:
        messages.error(request, "Resposta OAuth invalida.")
        return redirect("portal_login")

    try:
        user = exchange_code_for_user(request=request, code=code, state=state)
    except GoogleOAuthError as exc:
        log_security_event(
            "portal_b2c_google_exchange_failed",
            request=request,
            details={"reason": str(exc)[:100]},
        )
        messages.error(request, "Nao foi possivel concluir o login com Google.")
        return redirect("portal_login")

    just_created = bool(getattr(user, "_just_created_via_google", False))
    if just_created:
        # mesmo fluxo de consentimento automatico do cadastro por email
        consentimento_texto = (
            f"termos-v{PORTAL_B2C_TERMOS_VERSAO}|privacidade-v{PORTAL_B2C_TERMOS_VERSAO}|"
            f"optin-alerta-passagem|optin-artigo-novo|via=google"
        )
        hash_consentimento = _documento_hash(consentimento_texto)
        criar_opt_ins_no_cadastro(
            user,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            versao_termos=PORTAL_B2C_TERMOS_VERSAO,
            hash_termos=hash_consentimento,
            url_origem=get_request_url(request),
        )
        _send_confirmation_email(user, request)
        try:
            from portal.services.admin_notifications import enviar_email_admin_novo_cadastro
            enviar_email_admin_novo_cadastro(user, via="google")
        except Exception:  # noqa: BLE001
            pass

    login_portal_user(request, user)
    link_pre_user_to(user, request)

    stored_next = request.session.pop(PORTAL_SESSION_NEXT_KEY, "")
    destination = stored_next if is_safe_next(stored_next) else reverse("portal_home")
    if just_created:
        messages.success(request, "Conta criada via Google! Bem-vindo ao NC Fly.")
    return redirect(destination)


# ---------------------------------------------------------------------------
# Unsubscribe independente por canal
# ---------------------------------------------------------------------------


def _handle_unsubscribe(request, optin_model, token, label):
    optin = get_object_or_404(optin_model, token_unsubscribe=token)

    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "")[:80]
        optin.cancelar(ip=get_client_ip(request), motivo=motivo)
        log_security_event(
            "portal_b2c_optout",
            request=request,
            identifier=optin.email,
            details={"canal": label, "optin_id": optin.pk},
        )
        return render(
            request,
            "portal/auth/unsubscribe_result.html",
            {"canal": label, "email": optin.email, "cancelado": True},
        )

    return render(
        request,
        "portal/auth/unsubscribe_confirm.html",
        {"canal": label, "email": optin.email, "ja_cancelado": not optin.ativo},
    )


@require_http_methods(["GET", "POST"])
def portal_optout_alerta(request, token):
    return _handle_unsubscribe(request, OptInAlertaPassagem, token, "alertas de passagens")


@require_http_methods(["GET", "POST"])
def portal_optout_artigo(request, token):
    return _handle_unsubscribe(request, OptInArtigoNovo, token, "artigos novos")
