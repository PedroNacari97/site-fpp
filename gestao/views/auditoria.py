from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from .utils import admin_required
from ..models import AuditLog

@login_required
@user_passes_test(admin_required)
def admin_auditoria(request):
    logs = AuditLog.objects.select_related('user').all()
    return render(request, 'admin_custom/auditoria.html', {'logs': logs})
