import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "b", "i", "u", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6", "a", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td", "blockquote",
}
ALLOWED_ATTRS_RE = re.compile(r'\s(href|title|class|id)="[^"]*"')
TAG_RE = re.compile(r"<(/?)(\w+)([^>]*)>")


def _sanitize_tag(match):
    closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)
    if tag not in ALLOWED_TAGS:
        return ""
    safe_attrs = " ".join(ALLOWED_ATTRS_RE.findall(attrs)) if not closing else ""
    if safe_attrs:
        return f"<{closing}{tag} {safe_attrs}>"
    return f"<{closing}{tag}>"

FEATURE_LABELS = {
    "emissoes": "Emissoes de passagens",
    "cotacoes": "Cotacoes automatizadas",
    "clientes": "Gestao de clientes",
    "programas_fidelidade": "Programas de fidelidade",
    "pdf_profissional": "PDF profissional",
    "multi_operador": "Multi-operador",
    "relatorios": "Relatorios avancados",
    "hoteis": "Emissoes de hoteis",
    "api_integracao": "API de integracao",
    "suporte_prioritario": "Suporte prioritario",
    "marca_branca": "Marca branca (white-label)",
}


@register.filter
def safe_html(value):
    """Sanitiza HTML permitindo apenas tags seguras de formatacao."""
    if not value:
        return ""
    sanitized = TAG_RE.sub(_sanitize_tag, str(value))
    sanitized = re.sub(r"<script[^>]*>.*?</script>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r"<style[^>]*>.*?</style>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r"\bon\w+\s*=", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"javascript\s*:", "", sanitized, flags=re.IGNORECASE)
    return mark_safe(sanitized)


@register.filter
def feature_list(features_dict):
    """Converte o dict de features em lista de labels legiveis."""
    if not isinstance(features_dict, dict):
        return []
    return [
        FEATURE_LABELS.get(key, key.replace("_", " ").title())
        for key, enabled in features_dict.items()
        if enabled
    ]
