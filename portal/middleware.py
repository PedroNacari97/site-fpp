"""Middleware do Portal B2C.

Principal: `PreUserTrackingMiddleware` — registra todo visitante anonimo do
portal publico via cookie `pu_uid` (UUID v4) para medir taxa de conversao.

Regras:
- so atua em rotas publicas do portal (exclui /ncadm/, /adm/, /painel/,
  /django/admin/, /auth/, /webhooks/, /media/, /static/, /health/)
- cookie HttpOnly + SameSite=Lax + Secure em prod, 2 anos de validade
- bots (UA vazio ou contendo bot/crawler/spider) nao geram PreUser
- update de `ultimo_ip` / `ultima_url` / `total_visitas` throttled via cache
  (uma escrita a cada 60s por pre_user) — evita hot path de I/O em picos
- expoe `request.pre_user` para as views (login/cadastro linkam via helper)

LGPD: cookie tecnico de legitimo interesse. Descrito na Politica de Privacidade.
Nao requer consent banner (nao rastreia entre dominios).
"""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction


logger = logging.getLogger(__name__)


# Nome do cookie + metadados. Cookie tecnico — nao usa nome iniciado por "_ga"
# ou equivalentes a analytics de terceiros para deixar claro que e proprio.
PRE_USER_COOKIE_NAME = "pu_uid"
PRE_USER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 anos

# Janela de throttle de UPDATE (segundos). Em 1000 req/s isso reduz de 1000
# UPDATEs/s para no maximo 1 UPDATE/pre_user/60s.
PRE_USER_UPDATE_THROTTLE_SECONDS = 60

# Prefixos (path) que NAO recebem tracking. Mantemos o middleware barato
# em rotas privadas/administrativas/estaticos.
EXCLUDED_PATH_PREFIXES = (
    "/ncadm/",
    "/adm/",
    "/painel/",
    "/django/",
    "/auth/",
    "/accounts/",
    "/webhooks/",
    "/integracoes/",
    "/media/",
    "/static/",
    "/health/",
    "/robots.txt",
    "/ads.txt",
    "/llms.txt",
    "/sitemap.xml",
    "/favicon.ico",
)

# Filtro simples de bot por UA. Nao substitui fingerprint server-side serio;
# e so uma barreira pra nao poluir o banco com crawlers conhecidos.
BOT_UA_TOKENS = (
    "bot",
    "crawler",
    "spider",
    "slurp",
    "bingpreview",
    "facebookexternalhit",
    "pingdom",
    "uptimerobot",
    "headlesschrome",
    "phantomjs",
    "semrushbot",
    "ahrefs",
    "dotbot",
)


def _is_excluded_path(path: str) -> bool:
    if not path:
        return True
    for prefix in EXCLUDED_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_bot_ua(user_agent: str) -> bool:
    if not user_agent:
        return True
    ua_lower = user_agent.lower()
    return any(token in ua_lower for token in BOT_UA_TOKENS)


def _get_client_ip(request) -> str:
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "").strip()[:45]


def _current_url(request, max_length: int = 500) -> str:
    try:
        url = request.build_absolute_uri()
    except Exception:
        url = request.path or ""
    return (url or "")[:max_length]


def _referrer(request, max_length: int = 500) -> str:
    return (request.META.get("HTTP_REFERER") or "")[:max_length]


def _parse_uuid(raw) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _cookie_flags() -> dict:
    # Secure=True em producao (atrelado ao comportamento dos cookies de sessao).
    # SameSite=Lax permite leitura em navegacao top-level (ok para tracking).
    return {
        "max_age": PRE_USER_COOKIE_MAX_AGE,
        "httponly": True,
        "samesite": "Lax",
        "secure": bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        "path": "/",
    }


class PreUserTrackingMiddleware:
    """Grava visitantes anonimos do portal em `PreUser` via cookie `pu_uid`."""

    def __init__(self, get_response):
        self.get_response = get_response

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def __call__(self, request):
        # 1) caminho excluido: segue adiante sem setar request.pre_user
        if _is_excluded_path(request.path or ""):
            return self.get_response(request)

        # 2) UA de bot: ignora — nao cria, nao seta cookie, nao atualiza
        ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
        if _is_bot_ua(ua):
            request.pre_user = None
            return self.get_response(request)

        pre_user, needs_cookie_refresh = self._ensure_pre_user(request, ua)
        request.pre_user = pre_user

        response = self.get_response(request)

        if pre_user is not None and needs_cookie_refresh:
            response.set_cookie(
                PRE_USER_COOKIE_NAME,
                str(pre_user.uid),
                **_cookie_flags(),
            )
        return response

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    def _ensure_pre_user(self, request, user_agent: str):
        """Resolve (ou cria) o PreUser do request.

        Retorna (pre_user, needs_cookie_refresh). `pre_user` pode ser None
        se houve erro de banco (degrada silencioso — nao derruba o portal
        por causa de tracking).
        """
        from .models import PreUser  # import lazy — evita AppRegistryNotReady

        raw_cookie = request.COOKIES.get(PRE_USER_COOKIE_NAME)
        cookie_uid = _parse_uuid(raw_cookie)

        ip = _get_client_ip(request) or None
        url = _current_url(request)
        referrer = _referrer(request)
        utm_source = (request.GET.get("utm_source") or "")[:120]
        utm_medium = (request.GET.get("utm_medium") or "")[:120]
        utm_campaign = (request.GET.get("utm_campaign") or "")[:120]

        # --- caso 1: cookie valido, tenta encontrar ---
        if cookie_uid is not None:
            pre_user = self._load_pre_user(cookie_uid)
            if pre_user is not None:
                self._maybe_update(pre_user, ip=ip, url=url)
                return pre_user, False
            # cookie aponta pra UUID inexistente (banco zerado, migracao, etc.)
            # -> cria novo e reescreve cookie

        # --- caso 2: sem cookie OU cookie invalido -> cria ---
        try:
            with transaction.atomic():
                pre_user = PreUser.objects.create(
                    uid=uuid.uuid4(),
                    primeiro_ip=ip,
                    primeiro_ua=user_agent[:2000] if user_agent else "",
                    primeira_url=url,
                    primeiro_referrer=referrer,
                    utm_source=utm_source,
                    utm_medium=utm_medium,
                    utm_campaign=utm_campaign,
                    ultimo_ip=ip,
                    ultima_url=url,
                    total_visitas=1,
                )
        except DatabaseError:
            logger.warning("PreUser: falha ao criar (DB) — seguindo sem tracking", exc_info=True)
            return None, False

        # semeia cache para pular UPDATE redundante nos proximos 60s
        self._touch_cache(pre_user.uid)
        return pre_user, True

    def _load_pre_user(self, uid: uuid.UUID):
        from .models import PreUser

        try:
            return PreUser.objects.filter(uid=uid).first()
        except DatabaseError:
            logger.warning("PreUser: falha ao carregar por uid=%s", uid, exc_info=True)
            return None

    def _maybe_update(self, pre_user, *, ip, url):
        """Atualiza `ultimo_ip`/`ultima_url`/`total_visitas` com throttle via cache."""
        cache_key = self._cache_key(pre_user.uid)
        # cache indisponivel (ex.: tabela django_cache nao criada) nao pode
        # derrubar o portal. Em caso de falha, segue sem throttle.
        try:
            if cache.get(cache_key):
                return  # dentro da janela de throttle — nao escreve
        except Exception:
            logger.warning("PreUser: cache.get falhou — seguindo sem throttle", exc_info=True)
        try:
            from .models import PreUser

            # incrementa total_visitas atomicamente e atualiza campos
            # update_fields minimiza a escrita (3 colunas + atualizado_em)
            PreUser.objects.filter(pk=pre_user.pk).update(
                ultimo_ip=ip,
                ultima_url=url,
                total_visitas=models_expression_increment(),
            )
        except DatabaseError:
            logger.warning("PreUser: falha ao atualizar uid=%s", pre_user.uid, exc_info=True)
            return
        self._touch_cache(pre_user.uid)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _cache_key(uid: uuid.UUID) -> str:
        return f"pre_user:touch:{uid}"

    @classmethod
    def _touch_cache(cls, uid: uuid.UUID) -> None:
        try:
            cache.set(cls._cache_key(uid), 1, timeout=PRE_USER_UPDATE_THROTTLE_SECONDS)
        except Exception:
            # cache indisponivel nao pode derrubar o request
            pass


def models_expression_increment():
    """Retorna uma F-expression `F('total_visitas') + 1` — isolada pra permitir
    import lazy de django.db.models.F sem atrapalhar os imports do topo."""
    from django.db.models import F

    return F("total_visitas") + 1


# ----------------------------------------------------------------------------
# CanonicalHostMiddleware
# ----------------------------------------------------------------------------
# Forca um unico hostname canonico (ex: www.ncfly.com.br) via redirect 301
# permanente. Resolve o problema de SEO "Cópia, o Google escolheu uma página
# canônica diferente" causado por mesmo conteudo em www e naked.
#
# Configuracao via settings:
#   PORTAL_CANONICAL_HOST = "www.ncfly.com.br"   # host alvo
#   PORTAL_FORCE_CANONICAL_HOST = True           # liga/desliga (default False)
#
# Pula health-checks (Railway/Fastly) e qualquer host que nao esteja em
# ALLOWED_HOSTS — evita loop e falso positivo durante teste.
# ----------------------------------------------------------------------------


class CanonicalHostMiddleware:
    """Redireciona 301 para o host canonico configurado em settings.

    - Apenas em GET/HEAD (POST/PUT/DELETE com body redirecionado pode quebrar
      formularios/webhooks).
    - Pula /health/ (probes do Railway).
    - So redireciona se o host atual esta em ALLOWED_HOSTS — assim hosts
      desconhecidos (testes, ataques) nao sao atendidos com 301.
    """

    SAFE_METHODS = ("GET", "HEAD")
    SKIP_PATHS = ("/health/",)

    def __init__(self, get_response):
        from django.conf import settings

        self.get_response = get_response
        self.target_host = (getattr(settings, "PORTAL_CANONICAL_HOST", "") or "").lower().strip()
        self.enabled = bool(
            getattr(settings, "PORTAL_FORCE_CANONICAL_HOST", False) and self.target_host
        )

    def __call__(self, request):
        if self.enabled and request.method in self.SAFE_METHODS:
            host = request.get_host().lower()
            # Compara so o nome (ignora porta — em prod nao tem :8000)
            host_no_port = host.split(":", 1)[0]
            if host_no_port and host_no_port != self.target_host:
                if not any(request.path.startswith(p) for p in self.SKIP_PATHS):
                    from django.http import HttpResponsePermanentRedirect

                    new_url = "{scheme}://{host}{full_path}".format(
                        scheme="https" if request.is_secure() else "http",
                        host=self.target_host,
                        full_path=request.get_full_path(),
                    )
                    return HttpResponsePermanentRedirect(new_url)
        return self.get_response(request)
