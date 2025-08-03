from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ..models import AuditLog

@login_required
def admin_auditoria(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin" and not request.user.is_superuser:
        return render(request, "sem_permissao.html")
    logs = AuditLog.objects.select_related('user').all()
    return render(request, 'admin_custom/auditoria.html', {'logs': logs})
