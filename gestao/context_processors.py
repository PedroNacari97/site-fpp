from django.conf import settings

from gestao.services.dashboard import (
    build_operational_notifications,
    group_notifications_by_type,
)


def _resolve_user_empresa(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    cliente = getattr(user, "cliente_gestao", None)
    return getattr(cliente, "empresa", None) if cliente else None


def app_branding(request):
    empresa = _resolve_user_empresa(getattr(request, "user", None))
    default_logo_url = getattr(settings, "PORTAL_SITE_LOGO_URL", "/static/portal/img/nacari-fly-logo.webp")
    footer_logo_url = getattr(
        settings,
        "PORTAL_SITE_LOGO_LIGHT_URL",
        "/static/portal/img/nacari-fly-logo.webp",
    )
    custom_logo_url = getattr(empresa, "logo_documentos_url", "") if empresa else ""

    return {
        "app_branding": {
            "empresa": empresa,
            "logo_url": custom_logo_url or default_logo_url,
            "footer_logo_url": custom_logo_url or footer_logo_url,
            "default_logo_url": default_logo_url,
            "default_footer_logo_url": footer_logo_url,
            "has_custom_logo": bool(custom_logo_url),
            "name": getattr(empresa, "nome", "") or "Nacari Fly",
            "alt": getattr(empresa, "nome", "") or "Nacari Fly",
        }
    }


def admin_notifications(request):
    default_payload = {
        "admin_notifications": [],
        "admin_notifications_unread_count": 0,
        "admin_notifications_groups": [],
        "admin_notifications_recent": [],
    }

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return default_payload

    if not request.path.startswith("/adm/"):
        return default_payload

    if request.user.is_superuser:
        empresa = None
    else:
        perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
        if perfil not in {"admin", "operador"}:
            return default_payload
        empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)

    # Traz um volume maior para compor resumo agrupado; UI limita exibição.
    notifications = build_operational_notifications(
        user=request.user,
        empresa=empresa,
        limit=20,
    )
    groups = group_notifications_by_type(notifications)
    recent = notifications[:5]
    return {
        "admin_notifications": notifications[:6],
        "admin_notifications_unread_count": len(notifications),
        "admin_notifications_groups": groups,
        "admin_notifications_recent": recent,
    }
