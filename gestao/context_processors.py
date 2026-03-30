from gestao.services.dashboard import build_operational_notifications


def admin_notifications(request):
    default_payload = {
        "admin_notifications": [],
        "admin_notifications_unread_count": 0,
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

    notifications = build_operational_notifications(
        user=request.user,
        empresa=empresa,
        limit=6,
    )
    return {
        "admin_notifications": notifications,
        "admin_notifications_unread_count": len(notifications),
    }
