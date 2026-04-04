from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.access import user_has_admin_panel_access

from ..forms import DocumentoPlataformaForm
from ..models import AceiteDocumentoPlataforma, DocumentoPlataforma
from ..services.documentos_plataforma import get_documento_platform_url


def _require_superadmin(request):
    if not request.user.is_superuser or not user_has_admin_panel_access(request.user):
        return render(request, "sem_permissao.html")
    return None


@login_required
def governanca_plataforma(request):
    if (permission_denied := _require_superadmin(request)):
        return permission_denied

    documentos = list(DocumentoPlataforma.objects.order_by("tipo"))
    aceites_recentes = AceiteDocumentoPlataforma.objects.select_related(
        "empresa", "aceito_por", "documento"
    )[:20]

    context = {
        "menu_ativo": "governanca",
        "kpis": [
            {
                "label": "Camada SaaS",
                "value": "Superadmin",
                "description": "Governanca da plataforma, documentos-mestre e controle global.",
            },
            {
                "label": "Camada B2B",
                "value": "Admin da empresa",
                "description": "Uso da plataforma locada, operacao interna e dados do contratante.",
            },
            {
                "label": "Documentos publicos",
                "value": "Home",
                "description": "Sobre, privacidade e termos do portal editorial.",
            },
            {
                "label": "Documentos da plataforma",
                "value": "Area logada",
                "description": "Privacidade e termos especificos para login, auditoria e uso autenticado.",
            },
        ],
        "documentos_publicos": [
            {
                "label": "Sobre nos",
                "url": reverse("portal_sobre"),
                "escopo": "Portal publico",
                "descricao": "Posicionamento editorial, transparencia, publicidade e proposta do portal.",
            },
            {
                "label": "Politica de Privacidade",
                "url": reverse("portal_privacidade"),
                "escopo": "Portal publico",
                "descricao": "Cookies, analytics, navegacao publica e direitos do titular no site aberto.",
            },
            {
                "label": "Termos de Uso",
                "url": reverse("portal_termos"),
                "escopo": "Portal publico",
                "descricao": "Regras da home, noticias, links externos, publicidade e uso editorial.",
            },
        ],
        "documentos_plataforma": [
            {
                "documento": documento,
                "form": DocumentoPlataformaForm(instance=documento, prefix=f"doc-{documento.id}"),
                "url": get_documento_platform_url(documento.tipo),
            }
            for documento in documentos
        ],
        "aceites_recentes": aceites_recentes,
    }
    return render(request, "admin_custom/governanca_plataforma.html", context)


@login_required
def atualizar_documento_plataforma(request, documento_id):
    if (permission_denied := _require_superadmin(request)):
        return permission_denied
    documento = get_object_or_404(DocumentoPlataforma, id=documento_id)
    if request.method != "POST":
        return redirect("admin_governanca_plataforma")

    form = DocumentoPlataformaForm(request.POST, instance=documento, prefix=f"doc-{documento.id}")
    if form.is_valid():
        form.save()
        messages.success(request, f"{documento.get_tipo_display()} atualizado com sucesso.")
    else:
        messages.error(request, f"Nao foi possivel atualizar {documento.get_tipo_display().lower()}.")
    return redirect("admin_governanca_plataforma")
