import json
from .models import AuditLog

class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if request.path.startswith('/adm/') and request.user.is_authenticated:
                data = ''
                if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                    data = json.dumps(request.POST.dict())
                AuditLog.objects.create(
                    user=request.user,
                    path=request.path,
                    method=request.method,
                    data=data,
                )
        except Exception:
            pass
        return response
