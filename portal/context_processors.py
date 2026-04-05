from django.conf import settings
from django.urls import reverse

from .cookies import (
    analytics_cookies_allowed,
    get_cookie_preferences_from_request,
    has_cookie_preferences,
    normalize_cookie_preferences,
)


def portal_public_settings(request):
    from .views import CATEGORY_CONFIGS

    raw_cookie_preferences = get_cookie_preferences_from_request(request)
    cookie_preferences = normalize_cookie_preferences(raw_cookie_preferences)
    category_nav_labels = {
        "milhas-e-pontos": "Milhas",
        "cartoes-credito": "Cartões",
        "hoteis-resorts": "Hotéis",
    }
    return {
        "google_analytics_measurement_id": settings.GOOGLE_ANALYTICS_MEASUREMENT_ID,
        "google_search_console_verification": settings.GOOGLE_SEARCH_CONSOLE_VERIFICATION,
        "portal_legal_entity_name": settings.PORTAL_LEGAL_ENTITY_NAME,
        "portal_contact_email": settings.PORTAL_CONTACT_EMAIL,
        "portal_contact_phone": settings.PORTAL_CONTACT_PHONE,
        "portal_contact_whatsapp": settings.PORTAL_CONTACT_WHATSAPP,
        "portal_company_cnpj": settings.PORTAL_COMPANY_CNPJ,
        "portal_company_address": settings.PORTAL_COMPANY_ADDRESS,
        "portal_dpo_email": settings.PORTAL_DPO_EMAIL,
        "portal_site_logo_url": settings.PORTAL_SITE_LOGO_URL,
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
