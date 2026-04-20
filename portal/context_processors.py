from django.conf import settings
from django.urls import reverse

from .cookies import (
    analytics_cookies_allowed,
    get_cookie_preferences_from_request,
    has_cookie_preferences,
    normalize_cookie_preferences,
)


# Rotas que PODEM disparar GA4 (portal público indexável).
# Qualquer outra rota — inclusive /adm, /ncadm, /painel, /login, /accounts,
# /auth, /contratar, /assinatura, /webhooks, /integracoes, /monitoramento,
# /django/admin — NÃO deve injetar o measurement id.
_PUBLIC_PATH_PREFIXES = (
    "/home/",
    "/plataforma/",
)

# Paths públicos exatos (sem prefixo trailing).
_PUBLIC_EXACT_PATHS = {
    "/",
    "/sitemap.xml",
    "/robots.txt",
    "/ads.txt",
    "/llms.txt",
}

# Paths dentro do portal que, apesar de começarem com /home/, são privados
# (autenticação/fluxo interno) e não devem carregar GA4.
_PRIVATE_PORTAL_PREFIXES = (
    "/home/login/",
    "/home/cadastro/",
    "/home/auth/",
    "/home/logout/",
)


def _path_is_public(path: str) -> bool:
    """Retorna True quando o path pode disparar GA4 (página pública indexável)."""
    if not path:
        return False
    if any(path.startswith(prefix) for prefix in _PRIVATE_PORTAL_PREFIXES):
        return False
    if path in _PUBLIC_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


def portal_public_settings(request):
    from .auth import get_portal_user
    from .views import CATEGORY_CONFIGS

    raw_cookie_preferences = get_cookie_preferences_from_request(request)
    cookie_preferences = normalize_cookie_preferences(raw_cookie_preferences)
    ga_measurement_id = (
        settings.GOOGLE_ANALYTICS_MEASUREMENT_ID
        if _path_is_public(getattr(request, "path", "") or "")
        else ""
    )
    contact_whatsapp = settings.PORTAL_CONTACT_WHATSAPP or settings.PORTAL_CONTACT_PHONE
    category_nav_labels = {
        "milhas-e-pontos": "Milhas",
        "cartoes-credito": "Cartões",
        "hoteis-resorts": "Hotéis",
    }
    portal_user = get_portal_user(request)
    return {
        "portal_user": portal_user,
        "portal_user_authenticated": bool(portal_user),
        "google_analytics_measurement_id": ga_measurement_id,
        "google_search_console_verification": settings.GOOGLE_SEARCH_CONSOLE_VERIFICATION,
        "portal_legal_entity_name": settings.PORTAL_LEGAL_ENTITY_NAME,
        "portal_contact_email": settings.PORTAL_CONTACT_EMAIL,
        "portal_partnership_email": settings.PORTAL_PARTNERSHIP_EMAIL,
        "portal_contact_phone": settings.PORTAL_CONTACT_PHONE,
        "portal_contact_whatsapp": contact_whatsapp,
        "portal_company_cnpj": settings.PORTAL_COMPANY_CNPJ,
        "portal_company_address": settings.PORTAL_COMPANY_ADDRESS,
        "portal_dpo_email": settings.PORTAL_DPO_EMAIL,
        "portal_site_logo_url": settings.PORTAL_SITE_LOGO_URL,
        "portal_site_favicon_url": settings.PORTAL_SITE_FAVICON_URL,
        "portal_cookie_consent_name": settings.PORTAL_COOKIE_CONSENT_COOKIE_NAME,
        "portal_cookie_consent_version": settings.PORTAL_COOKIE_CONSENT_VERSION,
        "portal_cookie_consent_max_age_days": settings.PORTAL_COOKIE_CONSENT_MAX_AGE_DAYS,
        "portal_cookie_preferences": cookie_preferences,
        "portal_cookie_consent_exists": has_cookie_preferences(request),
        "portal_cookie_analytics_enabled": analytics_cookies_allowed(request),
        "public_nav_categories": [
            {
                "label": config["label"],
                "nav_label": category_nav_labels.get(slug, config["label"]),
                "icon_variant": config["icon_variant"],
                "slug": slug,
                "url": reverse("portal_categoria", kwargs={"categoria_slug": slug}),
            }
            for slug, config in CATEGORY_CONFIGS.items()
        ],
    }
