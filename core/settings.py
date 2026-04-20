from pathlib import Path
import os
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if override or key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")


def _should_load_local_env() -> bool:
    explicit_flag = os.environ.get("DJANGO_LOAD_DOTENV_LOCAL")
    if explicit_flag is not None:
        return explicit_flag.lower() in ("1", "true", "yes", "on")

    environment_hint = (
        os.environ.get("SITE_ENVIRONMENT")
        or os.environ.get("DJANGO_ENV")
        or ""
    ).strip().lower()
    if environment_hint:
        return environment_hint in {"local", "development", "dev"}

    # Se a execucao ja recebeu uma secret key explicita do ambiente, assume
    # contexto de deploy e nao carrega .env.local por padrao.
    return not bool(os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY"))


if _should_load_local_env():
    _load_env_file(BASE_DIR / ".env.local", override=True)


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def _env_list(name, default=None):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return list(default or [])
    return [item.strip() for item in raw_value.split(",") if item.strip()]


# DEBUG default = False (fail-safe). Ative explicitamente com DJANGO_DEBUG=1
# apenas em maquinas de desenvolvimento.
DEBUG = _env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "chave-super-secreta-para-dev"
    else:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY para execucao em producao.")

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["127.0.0.1", "localhost"] if DEBUG else [],
)

CSRF_TRUSTED_ORIGINS = _env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["http://127.0.0.1:8000", "http://localhost:8000"] if DEBUG else [],
)

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
PREPEND_WWW = _env_bool("PREPEND_WWW", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sitemaps",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",          # obrigatorio para django-allauth
    "portal",
    "painel_cliente",
    "gestao",
    "accounts",
    "storages",
    "superadmin",
    "onboarding",
    "design_system",
    # django-allauth (Google OAuth para superadmin)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

AUTHENTICATION_BACKENDS = [
    "accounts.backends.CPFBackend",
    "django.contrib.auth.backends.ModelBackend",
    # allauth usa ModelBackend por baixo; o adapter fica em SOCIALACCOUNT_ADAPTER
    "allauth.account.auth_backends.AuthenticationBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Tracking de visitantes anonimos do portal (cookie `pu_uid`).
    # Depende de CommonMiddleware para `request.build_absolute_uri` e precisa
    # rodar antes dos middlewares que podem retornar early (auth/paywall).
    "portal.middleware.PreUserTrackingMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # obrigatorio django-allauth >= 0.56
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.middleware.SingleSessionMiddleware",
    "accounts.middleware.SessionInactivityMiddleware",
    "accounts.middleware.AdminAreaAccessMiddleware",
    "accounts.middleware.PlatformDocumentAcceptanceMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "gestao.middleware.AuditLogMiddleware",
    "onboarding.middleware.AssinaturaAtivaMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "gestao.context_processors.app_branding",
                "gestao.context_processors.admin_notifications",
                "portal.context_processors.portal_public_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            ssl_require=not DEBUG,
        )
    }
    if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"].update(
            {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            }
        )
elif DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DB", "seu_banco"),
            "USER": os.getenv("MYSQL_USER", "seu_usuario"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", "sua_senha"),
            "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

GOOGLE_ANALYTICS_MEASUREMENT_ID = os.environ.get(
    "GOOGLE_ANALYTICS_MEASUREMENT_ID", ""
).strip().upper()
GOOGLE_SEARCH_CONSOLE_VERIFICATION = os.environ.get(
    "GOOGLE_SEARCH_CONSOLE_VERIFICATION", ""
).strip()

SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").strip().rstrip("/")
SITE_ENVIRONMENT = os.environ.get(
    "SITE_ENVIRONMENT",
    "local" if DEBUG else "production",
).strip().lower() or ("local" if DEBUG else "production")
PORTAL_SITE_NAME = os.environ.get("PORTAL_SITE_NAME", "NC Fly News").strip() or "NC Fly News"
PORTAL_SITE_LOGO_URL = os.environ.get(
    "PORTAL_SITE_LOGO_URL", "/static/portal/img/nacari-fly-logo.webp"
).strip()
PORTAL_SITE_LOGO_LIGHT_URL = os.environ.get(
    "PORTAL_SITE_LOGO_LIGHT_URL", "/static/portal/img/nacari-fly-logo.webp"
).strip()
PORTAL_SITE_FAVICON_URL = os.environ.get(
    "PORTAL_SITE_FAVICON_URL", "/static/portal/img/nacari-fly-favicon.png"
).strip()
PORTAL_DEFAULT_META_DESCRIPTION = (
    os.environ.get(
        "PORTAL_DEFAULT_META_DESCRIPTION",
        "Portal da NC Fly com notícias, promoções, milhas, cartões de crédito, hotéis e estratégias para viajar melhor.",
    ).strip()
    or "Portal da NC Fly com notícias, promoções, milhas, cartões de crédito, hotéis e estratégias para viajar melhor."
)

PORTAL_LEGAL_ENTITY_NAME = os.environ.get("PORTAL_LEGAL_ENTITY_NAME", "NC Fly").strip() or "NC Fly"
PORTAL_CONTACT_EMAIL = os.environ.get("PORTAL_CONTACT_EMAIL", "").strip()
PORTAL_PARTNERSHIP_EMAIL = os.environ.get("PORTAL_PARTNERSHIP_EMAIL", "").strip()
PORTAL_CONTACT_PHONE = os.environ.get("PORTAL_CONTACT_PHONE", "").strip()
PORTAL_CONTACT_WHATSAPP = os.environ.get("PORTAL_CONTACT_WHATSAPP", "").strip()
PORTAL_LEAD_NOTIFICATION_RECIPIENTS = _env_list(
    "PORTAL_LEAD_NOTIFICATION_RECIPIENTS",
    ["pdrnacari@gmail.com"],
)
PORTAL_COMPANY_CNPJ = os.environ.get("PORTAL_COMPANY_CNPJ", "").strip()
PORTAL_COMPANY_ADDRESS = os.environ.get("PORTAL_COMPANY_ADDRESS", "").strip()
PORTAL_DPO_EMAIL = os.environ.get("PORTAL_DPO_EMAIL", PORTAL_CONTACT_EMAIL).strip()
PORTAL_COOKIE_CONSENT_COOKIE_NAME = os.environ.get(
    "PORTAL_COOKIE_CONSENT_COOKIE_NAME", "ncfly_cookie_preferences"
).strip() or "ncfly_cookie_preferences"
PORTAL_COOKIE_CONSENT_VERSION = os.environ.get(
    "PORTAL_COOKIE_CONSENT_VERSION", "2026-04"
).strip() or "2026-04"
PORTAL_COOKIE_CONSENT_MAX_AGE_DAYS = int(
    os.environ.get("PORTAL_COOKIE_CONSENT_MAX_AGE_DAYS", "180")
)

SESSION_COOKIE_HTTPONLY = True
# SameSite=Lax e o default aceitavel para fluxos OAuth (Google). Mudar para
# "Strict" quebraria o retorno do callback do Google no login do superadmin.
# Defesa em profundidade vem de HttpOnly + Secure + MFA + LoginGuard.
SESSION_COOKIE_SAMESITE = os.environ.get("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.environ.get("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
# CSRF token precisa ser lido por JS em alguns fluxos (fetch com header
# X-CSRFToken). Mantemos HttpOnly=False mas permitimos override via env.
CSRF_COOKIE_HTTPONLY = _env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.environ.get(
    "DJANGO_SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
)
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.environ.get(
    "DJANGO_SECURE_COOP", "same-origin"
)
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True
    )
    SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Portal B2C — rate limit de cadastro/login (reusa LoginGuard do accounts/)
PORTAL_B2C_REGISTER_LIMIT = int(os.environ.get("PORTAL_B2C_REGISTER_LIMIT", "10"))
PORTAL_B2C_REGISTER_LOCKOUT_MINUTES = int(
    os.environ.get("PORTAL_B2C_REGISTER_LOCKOUT_MINUTES", "15")
)
PORTAL_B2C_TERMOS_VERSAO = os.environ.get("PORTAL_B2C_TERMOS_VERSAO", "2026-04").strip() or "2026-04"

# Portal B2C — Google OAuth (isolado do fluxo de superadmin via allauth)
# Callback URL: <SITE_BASE_URL>/home/auth/google/callback/
# Em dev, normalmente http://localhost:8000/home/auth/google/callback/
# Em prod, precisa ser cadastrado no Google Cloud Console.
PORTAL_GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "PORTAL_GOOGLE_OAUTH_REDIRECT_URI", ""
).strip()

SECURITY_LOGIN_FAILURE_LIMIT = int(os.environ.get("SECURITY_LOGIN_FAILURE_LIMIT", "5"))
SECURITY_LOGIN_LOCKOUT_MINUTES = int(os.environ.get("SECURITY_LOGIN_LOCKOUT_MINUTES", "15"))
SECURITY_PASSWORD_RESET_LIMIT = int(os.environ.get("SECURITY_PASSWORD_RESET_LIMIT", "3"))
SECURITY_PASSWORD_RESET_LOCKOUT_MINUTES = int(
    os.environ.get("SECURITY_PASSWORD_RESET_LOCKOUT_MINUTES", "30")
)
ADMIN_SESSION_IDLE_TIMEOUT_SECONDS = int(
    os.environ.get("ADMIN_SESSION_IDLE_TIMEOUT_SECONDS", str(30 * 60))
)
USER_SESSION_IDLE_TIMEOUT_SECONDS = int(
    os.environ.get("USER_SESSION_IDLE_TIMEOUT_SECONDS", str(60 * 60))
)
# Superadmin painel interno — somente este e-mail acessa /ncadm/
# Variavel de ambiente: SUPERADMIN_EMAIL
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "pedro@ncfly.com.br").strip().lower()

SUPERADMIN_MFA_ENABLED = _env_bool("SUPERADMIN_MFA_ENABLED", True)
SUPERADMIN_MFA_CODE_TTL_MINUTES = int(
    os.environ.get("SUPERADMIN_MFA_CODE_TTL_MINUTES", "10")
)
SUPERADMIN_MFA_ATTEMPT_LIMIT = int(
    os.environ.get("SUPERADMIN_MFA_ATTEMPT_LIMIT", "5")
)

TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "").strip()
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "").strip()
TURNSTILE_API_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_FAIL_OPEN = _env_bool("TURNSTILE_FAIL_OPEN", DEBUG)

# Token de reset de senha: expiracao curta para mitigar roubo de e-mail e
# tokens vazados em historico de navegador. Padrao: 30 minutos (override via env).
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", str(30 * 60)))

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()
RESEND_REQUEST_TIMEOUT = int(os.environ.get("RESEND_REQUEST_TIMEOUT", "15"))

_configured_email_backend = os.environ.get("DJANGO_EMAIL_BACKEND", "").strip()
_default_email_backend = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
if RESEND_API_KEY and (
    not _configured_email_backend
    or _configured_email_backend == "django.core.mail.backends.smtp.EmailBackend"
):
    _default_email_backend = "portal.email_backends.ResendEmailBackend"
elif _configured_email_backend:
    _default_email_backend = _configured_email_backend

EMAIL_BACKEND = _default_email_backend
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("DJANGO_EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _env_bool("DJANGO_EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.environ.get("DJANGO_EMAIL_TIMEOUT", "10"))


def _default_outbound_email():
    if SITE_BASE_URL:
        hostname = (urlparse(SITE_BASE_URL).hostname or "").strip().lower()
        if hostname and hostname not in {"127.0.0.1", "localhost"}:
            return f"contato@{hostname}"
    return "contato@ncfly.com.br"


DEFAULT_FROM_EMAIL = (
    os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "").strip()
    or RESEND_FROM_EMAIL
    or EMAIL_HOST_USER.strip()
    or _default_outbound_email()
)
# Email de suporte usado para mensagens transacionais sensíveis (password reset e MFA).
# IMPORTANTE: o MX/DKIM/SPF de suporte@ncfly.com.br precisa estar configurado no
# provedor SMTP (Resend, SES, etc.) para evitar bloqueios por SPAM.
SUPPORT_FROM_EMAIL = (
    os.environ.get("SUPPORT_FROM_EMAIL", "").strip()
    or "suporte@ncfly.com.br"
)
PASSWORD_RESET_FROM_EMAIL = (
    os.environ.get("PASSWORD_RESET_FROM_EMAIL", "").strip()
    or SUPPORT_FROM_EMAIL
)
PORTAL_ALERTS_FROM_EMAIL = (
    os.environ.get("PORTAL_ALERTS_FROM_EMAIL", "alertas@ncfly.com.br").strip()
    or DEFAULT_FROM_EMAIL
)
PORTAL_ALERTS_REPLY_TO = (
    os.environ.get("PORTAL_ALERTS_REPLY_TO", PORTAL_CONTACT_EMAIL).strip()
)

# Monitoramento de passagens (SaaS B2B): envelope-from usado nos emails de alerta
# disparados pelo modulo gestao.services.monitoring. O nome exibido no remetente
# eh sempre o da agencia (Empresa); este endereco eh apenas o envelope tecnico.
# Reply-To aponta para empresa.email_contato em runtime.
MONITORAMENTO_ALERTAS_FROM_EMAIL = (
    os.environ.get("MONITORAMENTO_ALERTAS_FROM_EMAIL", "").strip()
    or PORTAL_ALERTS_FROM_EMAIL
)

TELEGRAM_ALERTS_BOT_TOKEN = os.environ.get("TELEGRAM_ALERTS_BOT_TOKEN", "")
TELEGRAM_ALERTS_WEBHOOK_SECRET = os.environ.get("TELEGRAM_ALERTS_WEBHOOK_SECRET", "")
TELEGRAM_ALERTS_ALLOWED_CHAT_IDS = _env_list("TELEGRAM_ALERTS_ALLOWED_CHAT_IDS", [])
TELEGRAM_NEWS_BOT_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
TELEGRAM_NEWS_WEBHOOK_SECRET = os.environ.get("TELEGRAM_NEWS_WEBHOOK_SECRET", "")
TELEGRAM_NEWS_ALLOWED_CHAT_IDS = _env_list("TELEGRAM_NEWS_ALLOWED_CHAT_IDS", [])

# Bot publico de consulta de status de voo (passageiro digita PNR + sobrenome)
TELEGRAM_STATUS_VOO_BOT_TOKEN = os.environ.get("TELEGRAM_STATUS_VOO_BOT_TOKEN", "")

# Instagram — Meta Graph API
# PAGE_ID e IG_USER_ID já conhecidos; ACCESS_TOKEN deve ser configurado no Railway.
INSTAGRAM_PAGE_ID = os.environ.get("INSTAGRAM_PAGE_ID", "1110876808770326").strip()
INSTAGRAM_IG_USER_ID = os.environ.get("INSTAGRAM_IG_USER_ID", "17841433241423866").strip()
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
INSTAGRAM_AUTO_PUBLISH = _env_bool("INSTAGRAM_AUTO_PUBLISH", True)
INSTAGRAM_PUBLISH_STORY = _env_bool("INSTAGRAM_PUBLISH_STORY", True)
INSTAGRAM_PUBLISH_RETRIES = int(os.environ.get("INSTAGRAM_PUBLISH_RETRIES", "3"))

if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.environ.get(
        "AWS_S3_CUSTOM_DOMAIN", f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    )
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
else:
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "painel_cliente/static"]
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = os.environ.get("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_CACHE_URL = os.environ.get("DJANGO_CACHE_URL", "").strip()
if _CACHE_URL.startswith("redis://") or _CACHE_URL.startswith("rediss://"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _CACHE_URL,
        }
    }
else:
    # DatabaseCache: compartilhado entre processos/workers sem custo extra
    # (usa o Postgres do Railway). Requer rodar `python manage.py
    # createcachetable` uma vez para criar a tabela `django_cache`.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
        }
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.template": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

LOGIN_URL = reverse_lazy("login_custom")
LOGIN_REDIRECT_URL = reverse_lazy("painel_dashboard")
LOGOUT_REDIRECT_URL = reverse_lazy("login_custom")

# ---------------------------------------------------------------------------
# django-allauth — Google OAuth (usado para login do superadmin)
# ---------------------------------------------------------------------------
# Variaveis de ambiente necessarias no Railway:
#   GOOGLE_OAUTH_CLIENT_ID      — Client ID do app no Google Cloud Console
#   GOOGLE_OAUTH_CLIENT_SECRET  — Client Secret do app no Google Cloud Console
#
# No Google Cloud Console (console.cloud.google.com), em:
#   APIs e servicos > Credenciais > OAuth 2.0 > URIs de redirecionamento autorizados
# Adicionar:
#   https://<seu-dominio>/auth/google/login/callback/
#
# SITE_ID=1 corresponde ao primeiro registro em django.contrib.sites.Site.
# Em producao, ajustar o domain via shell:
#   from django.contrib.sites.models import Site
#   Site.objects.update_or_create(pk=1, defaults={"domain": "ncfly.com.br", "name": "NCfly"})
# ---------------------------------------------------------------------------
SITE_ID = 1  # obrigatorio para django-allauth

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# allauth: nao criar automaticamente usuarios via social login —
# o superadmin ja existe no banco; o login social apenas autentica.
SOCIALACCOUNT_AUTO_SIGNUP = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"

# Adapter customizado: rejeita qualquer e-mail diferente de SUPERADMIN_EMAIL
SOCIALACCOUNT_ADAPTER = "superadmin.adapters.SuperadminOnlySocialAccountAdapter"
