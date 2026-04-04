from __future__ import annotations

import json
from urllib.parse import unquote

from django.conf import settings


DEFAULT_COOKIE_PREFERENCES = {
    "essential": True,
    "analytics": True,
}


def normalize_cookie_preferences(preferences: dict | None) -> dict[str, bool]:
    merged = dict(DEFAULT_COOKIE_PREFERENCES)
    for key in ("analytics",):
        merged[key] = bool((preferences or {}).get(key, merged[key]))
    merged["essential"] = True
    return merged


def get_cookie_preferences_from_request(request) -> dict[str, bool]:
    raw_value = request.COOKIES.get(settings.PORTAL_COOKIE_CONSENT_COOKIE_NAME, "")
    if not raw_value:
        return dict(DEFAULT_COOKIE_PREFERENCES)  # aceito tudo por padrão

    try:
        parsed = json.loads(unquote(raw_value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return dict(DEFAULT_COOKIE_PREFERENCES)

    if not isinstance(parsed, dict):
        return dict(DEFAULT_COOKIE_PREFERENCES)

    if parsed.get("version") != settings.PORTAL_COOKIE_CONSENT_VERSION:
        return dict(DEFAULT_COOKIE_PREFERENCES)

    return normalize_cookie_preferences(parsed)


def has_cookie_preferences(request) -> bool:
    raw_value = request.COOKIES.get(settings.PORTAL_COOKIE_CONSENT_COOKIE_NAME, "")
    return bool(raw_value)


def analytics_cookies_allowed(request) -> bool:
    preferences = get_cookie_preferences_from_request(request)
    return bool(preferences.get("analytics"))
