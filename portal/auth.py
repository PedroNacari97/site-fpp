"""Autenticacao isolada do Portal B2C.

Este modulo NAO depende do `auth.User` do Django nem do fluxo do SaaS B2B.
O login do portal usa uma chave propria na sessao (`PORTAL_SESSION_USER_KEY`)
para evitar qualquer colisao com `_auth_user_id` do Django.

Fluxos cobertos:
- login por email + senha
- cadastro por email + senha
- login/cadastro via Google OAuth (verificacao de id_token)
- logout (flush parcial da chave do portal, sem derrubar sessao do SaaS se
  estiverem no mesmo browser)

Rate-limit reutiliza `accounts.security.LoginGuard` com `scope` proprio
(`portal_b2c_login`, `portal_b2c_register`).
"""
from __future__ import annotations

import functools
import hashlib
import json
import secrets
from typing import Optional
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from accounts.security import (
    get_client_ip,
    get_user_agent,
    is_login_allowed,
    log_security_event,
    register_login_failure,
    register_security_action_attempt,
    reset_login_failures,
)

from .models import PortalUser


PORTAL_SESSION_USER_KEY = "portal_b2c_user_id"
PORTAL_SESSION_GOOGLE_STATE_KEY = "portal_b2c_oauth_state"
PORTAL_SESSION_GOOGLE_NONCE_KEY = "portal_b2c_oauth_nonce"
PORTAL_SESSION_NEXT_KEY = "portal_b2c_next"

LOGIN_SCOPE = "portal_b2c_login"
REGISTER_SCOPE = "portal_b2c_register"


# ---------------------------------------------------------------------------
# Sessao
# ---------------------------------------------------------------------------


def get_portal_user(request: HttpRequest) -> Optional[PortalUser]:
    """Recupera o `PortalUser` logado na sessao (ou None)."""
    cached = getattr(request, "_portal_user_cache", None)
    if cached is not None:
        return cached if cached.ativo else None

    user_id = request.session.get(PORTAL_SESSION_USER_KEY)
    if not user_id:
        request._portal_user_cache = None
        return None
    try:
        user = PortalUser.objects.get(pk=user_id, ativo=True)
    except PortalUser.DoesNotExist:
        # sessao resfriada — limpa
        request.session.pop(PORTAL_SESSION_USER_KEY, None)
        request._portal_user_cache = None
        return None
    request._portal_user_cache = user
    return user


def login_portal_user(request: HttpRequest, user: PortalUser) -> None:
    """Efetiva o login na sessao e rotaciona o session key (session fixation)."""
    # rotaciona o cookie de sessao para evitar session fixation
    try:
        request.session.cycle_key()
    except Exception:
        # algumas engines nao suportam cycle_key — nesse caso, flush preserva chaves
        request.session.flush()
    request.session[PORTAL_SESSION_USER_KEY] = user.pk
    request.session.modified = True
    request._portal_user_cache = user
    user.marcar_login(ip=get_client_ip(request))


def logout_portal_user(request: HttpRequest) -> None:
    """Encerra a sessao do Portal sem afetar outras apps.

    Se a sessao so tiver a chave do Portal, faz flush completo. Caso contrario
    remove apenas a chave e rotaciona para encerrar rastro.
    """
    request.session.pop(PORTAL_SESSION_USER_KEY, None)
    request._portal_user_cache = None
    # flush total sempre — logout deve invalidar a sessao inteira (security.md)
    request.session.flush()


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def portal_login_required(view_func):
    """Garante que a view so seja acessada por PortalUser autenticado."""

    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_portal_user(request) is None:
            login_url = reverse("portal_login")
            next_path = request.get_full_path()
            return HttpResponseRedirect(f"{login_url}?next={next_path}")
        return view_func(request, *args, **kwargs)

    return _wrapped


# ---------------------------------------------------------------------------
# Email/senha — cadastro e login
# ---------------------------------------------------------------------------


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def is_safe_next(url: str) -> bool:
    """So aceita paths internos (`/algo`) — bloqueia open redirect."""
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.netloc and not parsed.scheme and url.startswith("/")


def register_email_user(
    *,
    request: HttpRequest,
    email: str,
    nome: str,
    senha: str,
) -> PortalUser:
    """Cria um novo PortalUser com senha PBKDF2.

    Levanta `ValueError` se email ja existe.
    """
    email = normalize_email(email)
    if PortalUser.objects.filter(email=email).exists():
        raise ValueError("email_ja_cadastrado")

    ip = get_client_ip(request)
    ua = get_user_agent(request)

    user = PortalUser(
        email=email,
        nome=(nome or "").strip()[:180],
        email_verificado=False,
        ativo=True,
        ip_cadastro=ip,
        user_agent_cadastro=ua,
        source_environment=getattr(settings, "SITE_ENVIRONMENT", "local"),
        source_host=(request.get_host() or "")[:120],
    )
    user.set_password(senha)
    user.save()
    log_security_event(
        "portal_b2c_register_success",
        request=request,
        identifier=email,
        details={"user_id": user.pk},
    )
    return user


def authenticate_email_user(
    *,
    request: HttpRequest,
    email: str,
    senha: str,
) -> Optional[PortalUser]:
    email = normalize_email(email)
    try:
        user = PortalUser.objects.get(email=email, ativo=True)
    except PortalUser.DoesNotExist:
        register_login_failure(
            request, email, LOGIN_SCOPE, reason="unknown_email"
        )
        return None
    if not user.check_password(senha):
        register_login_failure(
            request, email, LOGIN_SCOPE, reason="invalid_password"
        )
        return None
    reset_login_failures(request, email, LOGIN_SCOPE)
    return user


def check_login_allowed(request: HttpRequest, email: str):
    return is_login_allowed(request, email, LOGIN_SCOPE)


def register_register_attempt(request: HttpRequest, email: str) -> None:
    register_security_action_attempt(
        request,
        email,
        REGISTER_SCOPE,
        limit=int(getattr(settings, "PORTAL_B2C_REGISTER_LIMIT", 10)),
        lockout_minutes=int(getattr(settings, "PORTAL_B2C_REGISTER_LOCKOUT_MINUTES", 15)),
        event_prefix="portal_b2c_register",
    )


def check_register_allowed(request: HttpRequest, email: str):
    from accounts.security import is_security_action_allowed
    return is_security_action_allowed(request, email, REGISTER_SCOPE)


# ---------------------------------------------------------------------------
# Google OAuth 2.0 — fluxo nativo (sem allauth) para NAO reaproveitar sessao
# de superadmin / agencias. Valida id_token contra os certificados publicos
# do Google (tokeninfo) — sem depender de biblioteca externa.
# ---------------------------------------------------------------------------


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleOAuthError(Exception):
    """Falha durante o fluxo OAuth do Google."""


def google_oauth_configured() -> bool:
    return bool(
        getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    )


def _portal_redirect_uri(request: HttpRequest) -> str:
    """Redirect URI do callback — sempre absoluto."""
    configured = (getattr(settings, "PORTAL_GOOGLE_OAUTH_REDIRECT_URI", "") or "").strip()
    if configured:
        return configured
    return request.build_absolute_uri(reverse("portal_google_callback"))


def build_google_authorize_url(request: HttpRequest, *, next_url: str = "") -> str:
    """Monta a URL de inicio do fluxo Google com `state` anti-CSRF e `nonce`."""
    if not google_oauth_configured():
        raise GoogleOAuthError("google_oauth_nao_configurado")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16)
    request.session[PORTAL_SESSION_GOOGLE_STATE_KEY] = state
    request.session[PORTAL_SESSION_GOOGLE_NONCE_KEY] = nonce
    if next_url and is_safe_next(next_url):
        request.session[PORTAL_SESSION_NEXT_KEY] = next_url
    request.session.modified = True

    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": _portal_redirect_uri(request),
        "state": state,
        "nonce": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _post(url: str, data: dict, timeout: int = 8) -> dict:
    """POST urlencoded — usa `requests` se disponivel, senao urllib."""
    try:
        import requests as req_lib
        resp = req_lib.post(url, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        import urllib.request
        import urllib.parse
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def _get(url: str, params: dict, timeout: int = 8) -> dict:
    try:
        import requests as req_lib
        resp = req_lib.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        import urllib.request
        import urllib.parse
        full = f"{url}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(full, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def exchange_code_for_user(
    *,
    request: HttpRequest,
    code: str,
    state: str,
) -> PortalUser:
    """Troca `code` por `id_token`, valida e cria/recupera PortalUser.

    Levanta `GoogleOAuthError` em qualquer falha.
    """
    if not google_oauth_configured():
        raise GoogleOAuthError("google_oauth_nao_configurado")

    expected_state = request.session.pop(PORTAL_SESSION_GOOGLE_STATE_KEY, None)
    expected_nonce = request.session.pop(PORTAL_SESSION_GOOGLE_NONCE_KEY, None)
    request.session.modified = True
    if not expected_state or not secrets.compare_digest(str(expected_state), str(state or "")):
        raise GoogleOAuthError("state_mismatch")

    try:
        token_response = _post(
            GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": _portal_redirect_uri(request),
                "grant_type": "authorization_code",
            },
        )
    except Exception as exc:
        raise GoogleOAuthError(f"token_exchange_failed:{exc.__class__.__name__}")

    id_token = token_response.get("id_token")
    if not id_token:
        raise GoogleOAuthError("missing_id_token")

    # Verifica o id_token via endpoint tokeninfo — valida assinatura e audience
    try:
        payload = _get(GOOGLE_TOKENINFO_URL, {"id_token": id_token})
    except Exception as exc:
        raise GoogleOAuthError(f"tokeninfo_failed:{exc.__class__.__name__}")

    if payload.get("aud") != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleOAuthError("audience_mismatch")
    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleOAuthError("issuer_mismatch")
    if expected_nonce and payload.get("nonce") and not secrets.compare_digest(
        str(expected_nonce), str(payload.get("nonce"))
    ):
        raise GoogleOAuthError("nonce_mismatch")

    email = normalize_email(payload.get("email") or "")
    email_verified = str(payload.get("email_verified", "")).lower() in ("true", "1")
    sub = (payload.get("sub") or "").strip()
    nome = (payload.get("name") or payload.get("given_name") or "").strip()[:180]

    if not email or not sub:
        raise GoogleOAuthError("missing_email_or_sub")
    if not email_verified:
        raise GoogleOAuthError("email_nao_verificado")

    ip = get_client_ip(request)
    ua = get_user_agent(request)

    # Busca por google_sub primeiro (mais estavel), depois por email
    user = PortalUser.objects.filter(google_sub=sub).first()
    if user is None:
        user = PortalUser.objects.filter(email=email).first()

    if user is None:
        user = PortalUser.objects.create(
            email=email,
            nome=nome,
            google_sub=sub,
            email_verificado=True,
            ativo=True,
            ip_cadastro=ip,
            user_agent_cadastro=ua,
            source_environment=getattr(settings, "SITE_ENVIRONMENT", "local"),
            source_host=(request.get_host() or "")[:120],
        )
        log_security_event(
            "portal_b2c_google_signup",
            request=request,
            identifier=email,
            details={"user_id": user.pk, "sub_hash": hashlib.sha256(sub.encode()).hexdigest()[:16]},
        )
        created = True
    else:
        created = False
        update_fields = []
        if not user.google_sub:
            user.google_sub = sub
            update_fields.append("google_sub")
        if not user.email_verificado and email_verified:
            user.email_verificado = True
            update_fields.append("email_verificado")
        if nome and not user.nome:
            user.nome = nome
            update_fields.append("nome")
        if update_fields:
            update_fields.append("atualizado_em")
            user.save(update_fields=update_fields)
        log_security_event(
            "portal_b2c_google_login",
            request=request,
            identifier=email,
            details={"user_id": user.pk},
        )

    user._just_created_via_google = created  # type: ignore[attr-defined]
    return user
