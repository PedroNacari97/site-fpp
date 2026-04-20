from decimal import Decimal, InvalidOperation

from django.urls import reverse

from accounts.security import get_client_ip, get_request_url, get_user_agent

from ..models import AceiteDocumentoPlataforma, DocumentoPlataforma


DOCUMENTO_ROUTE_MAP = {
    DocumentoPlataforma.TIPO_TERMOS: "portal_termos_plataforma",
    DocumentoPlataforma.TIPO_PRIVACIDADE: "portal_privacidade_plataforma",
    DocumentoPlataforma.TIPO_DPA: "portal_dpa_plataforma",
    DocumentoPlataforma.TIPO_SEGURANCA: "portal_seguranca_plataforma",
}


def get_documento_platform_url_name(tipo):
    return DOCUMENTO_ROUTE_MAP.get(tipo, "")


def get_documento_platform_url(tipo):
    route_name = get_documento_platform_url_name(tipo)
    return reverse(route_name) if route_name else "#"


def list_documentos_plataforma():
    return list(DocumentoPlataforma.objects.filter(ativo=True).order_by("tipo"))


def list_documentos_exigem_aceite():
    return list(
        DocumentoPlataforma.objects.filter(
            ativo=True,
            exige_aceite_empresa=True,
        ).order_by("tipo")
    )


def get_documento_por_tipo(tipo):
    return DocumentoPlataforma.objects.filter(tipo=tipo, ativo=True).first()


def get_pendencias_aceite_empresa(user):
    cliente = getattr(user, "cliente_gestao", None)
    empresa = getattr(cliente, "empresa", None)
    perfil = getattr(cliente, "perfil", "")
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if user.is_superuser or perfil != "admin" or empresa is None:
        return []
    if empresa.admin_id != getattr(cliente, "id", None):
        return []

    pendentes = []
    for documento in list_documentos_exigem_aceite():
        ja_aceito = AceiteDocumentoPlataforma.objects.filter(
            empresa=empresa,
            documento=documento,
            versao_aceita=documento.versao_atual,
        ).exists()
        if not ja_aceito:
            pendentes.append(documento)
    return pendentes


def empresa_tem_pendencia_aceite(user):
    return bool(get_pendencias_aceite_empresa(user))


def _clean_accept_metadata_value(value, max_length=0):
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned[:max_length] if max_length else cleaned


def _clean_accept_decimal(value):
    cleaned = str(value or "").strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def registrar_aceites_empresa(request, user, documentos):
    cliente = getattr(user, "cliente_gestao", None)
    empresa = getattr(cliente, "empresa", None)
    if empresa is None:
        return

    ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    url_origem = get_request_url(request)
    device_metadata = {
        "device_type": _clean_accept_metadata_value(request.POST.get("device_type"), 20),
        "browser_name": _clean_accept_metadata_value(request.POST.get("browser_name"), 60),
        "browser_version": _clean_accept_metadata_value(request.POST.get("browser_version"), 60),
        "os_name": _clean_accept_metadata_value(request.POST.get("os_name"), 60),
        "os_version": _clean_accept_metadata_value(request.POST.get("os_version"), 60),
        "device_language": _clean_accept_metadata_value(request.POST.get("device_language"), 40),
        "device_timezone": _clean_accept_metadata_value(request.POST.get("device_timezone"), 80),
        "screen_resolution": _clean_accept_metadata_value(request.POST.get("screen_resolution"), 40),
        "geolocation_status": _clean_accept_metadata_value(request.POST.get("geolocation_status"), 20),
        "latitude": _clean_accept_decimal(request.POST.get("latitude")),
        "longitude": _clean_accept_decimal(request.POST.get("longitude")),
        "geolocation_accuracy_meters": _clean_accept_decimal(request.POST.get("geolocation_accuracy_meters")),
    }
    for documento in documentos:
        AceiteDocumentoPlataforma.objects.get_or_create(
            empresa=empresa,
            documento=documento,
            versao_aceita=documento.versao_atual,
            defaults={
                "aceito_por": user,
                "ip_aceite": ip,
                "user_agent_aceite": user_agent,
                "url_origem": url_origem,
                **device_metadata,
            },
        )
