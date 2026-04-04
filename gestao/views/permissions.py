from django.db.models import Q
from django.shortcuts import render

from accounts.access import user_has_admin_panel_access


def require_admin_or_operator(request):
    if not user_has_admin_panel_access(request.user):
        return render(request, "sem_permissao.html")
    return None


def get_request_empresa(request):
    return getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)


def is_superadmin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_superuser)


def _extract_object_empresa(obj):
    if obj is None:
        return None

    empresa = getattr(obj, "empresa", None)
    if empresa is not None:
        return empresa

    for related_name in ("cliente", "conta_administrada", "emissor_parceiro"):
        related = getattr(obj, related_name, None)
        if related is None:
            continue
        related_empresa = getattr(related, "empresa", None)
        if related_empresa is not None:
            return related_empresa
    return None


def ensure_company_access(request, obj):
    empresa = get_request_empresa(request)
    if is_superadmin(request.user) or empresa is None:
        return None

    object_empresa = _extract_object_empresa(obj)
    if object_empresa is not None and object_empresa != empresa:
        return render(request, "sem_permissao.html")
    return None


def scope_queryset_to_company(queryset, request, *lookups):
    empresa = get_request_empresa(request)
    if is_superadmin(request.user) or empresa is None:
        return queryset

    if not lookups:
        lookups = ("empresa", "cliente__empresa", "conta_administrada__empresa", "emissor_parceiro__empresa")

    condition = Q()
    for lookup in lookups:
        condition |= Q(**{lookup: empresa})
    return queryset.filter(condition)
