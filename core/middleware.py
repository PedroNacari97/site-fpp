from django.conf import settings


class SecurityHeadersMiddleware:
    """Injeta headers de segurança adicionais em todas as respostas."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "CONTENT_SECURITY_POLICY", "")

    def __call__(self, request):
        response = self.get_response(request)
        if self.csp:
            response["Content-Security-Policy"] = self.csp
        return response
