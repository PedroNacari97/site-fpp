import json
from .models import AuditLog


SENSITIVE_KEYS = {
    "password",
    "senha",
    "identifier",
    "mfa_code",
    "csrfmiddlewaretoken",
}


def _sanitize_payload(raw_payload):
    sanitized = {}
    for key, value in raw_payload.items():
        sanitized[key] = "***" if key.lower() in SENSITIVE_KEYS else value
    return sanitized


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if request.path.startswith('/adm/') and request.user.is_authenticated:
                data = ''
                if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                    data = json.dumps(
                        {
                            "payload": _sanitize_payload(request.POST.dict()),
                            "ip_address": request.META.get("REMOTE_ADDR", ""),
                            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                        }
                    )
                AuditLog.objects.create(
                    user=request.user,
                    path=request.path,
                    method=request.method,
                    data=data,
                )
        except Exception:
            pass
        return response
