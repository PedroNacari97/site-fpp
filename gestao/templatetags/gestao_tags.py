from django import template

from ..utils import format_cpf_display, is_fake_cpf, normalize_cpf

register = template.Library()


@register.filter(name="cpf_display")
def cpf_display(value, fallback="--"):
    """Formata CPF para exibição. Oculta CPFs fake (que começam com 9)."""
    return format_cpf_display(value or "", fallback=fallback)


@register.filter(name="cpf_is_fake")
def cpf_is_fake(value):
    """True se o CPF é interno (fake) — útil em templates para esconder CPFs gerados."""
    return is_fake_cpf(value or "")


@register.filter(name="cpf_or_none")
def cpf_or_none(value):
    """Retorna CPF formatado ou string vazia se fake/inválido."""
    digits = normalize_cpf(value or "")
    if len(digits) == 11 and not digits.startswith("9"):
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return ""


_NOTIF_TONE_MAP = {
    "cotacao_nova": "blue",
    "cotacao_aprovada": "green",
    "cotacao_vencendo": "amber",
    "emissao_concluida": "green",
    "emissao_pendente": "amber",
    "alerta_passagem": "violet",
    "cliente_cadastrado": "blue",
    "clube_vencendo": "amber",
    "saldo_baixo": "red",
    "sistema": "slate",
    "outros": "slate",
}

_NOTIF_ICON_MAP = {
    "cotacao_nova": "C",
    "cotacao_aprovada": "✓",
    "cotacao_vencendo": "⏰",
    "emissao_concluida": "✓",
    "emissao_pendente": "!",
    "alerta_passagem": "★",
    "cliente_cadastrado": "U",
    "clube_vencendo": "⏰",
    "saldo_baixo": "!",
    "sistema": "i",
    "outros": "•",
}


@register.filter(name="notif_tone")
def notif_tone(tipo):
    """Mapeia tipo de notificação para tonalidade visual."""
    return _NOTIF_TONE_MAP.get(str(tipo or "").lower(), "slate")


@register.filter(name="notif_icon")
def notif_icon(tipo):
    """Mapeia tipo de notificação para glifo compacto."""
    return _NOTIF_ICON_MAP.get(str(tipo or "").lower(), "•")
