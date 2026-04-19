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
