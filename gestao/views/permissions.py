from django.shortcuts import render


def require_admin_or_operator(request):
    """Return a permission error page if the user lacks admin privileges.

    Superusers are allowed access. For regular users we check the associated
    ``cliente_gestao`` profile and ensure the ``perfil`` is either ``admin`` or
    ``operador``. If the user does not have the required role, the standard
    "sem_permissao.html" template is rendered.
    """
    if request.user.is_superuser:
        return render(request, "sem_permissao.html")
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil not in ["admin", "operador"]:
        return render(request, "sem_permissao.html")
    return None
