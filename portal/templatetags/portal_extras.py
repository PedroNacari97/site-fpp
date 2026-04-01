import re
from datetime import date, datetime

from django import template
from django.utils import timezone


register = template.Library()

MONTHS_PT_BR = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

DISPLAY_LABELS = {
    "Milhas e Pontos": "Milhas e Pontos",
    "Promocoes": "Promoções",
    "Promocao": "Promoção",
    "Cartoes de Credito": "Cartões de Crédito",
    "Cartoes": "Cartões",
    "Credito": "Crédito",
    "Hoteis e Resorts": "Hotéis e Resorts",
    "Hoteis": "Hotéis",
    "Noticias": "Notícias",
    "Noticia": "Notícia",
    "Transferencias Bonificadas": "Transferências Bonificadas",
    "Transferencias e Bonus": "Transferências e Bônus",
    "Programas de Fidelidade": "Programas de Fidelidade",
    "Emissoes e Resgates": "Emissões e Resgates",
    "Clubes e Assinaturas": "Clubes e Assinaturas",
    "Salas VIP e Beneficios": "Salas VIP e Benefícios",
    "Compra e Venda de Pontos": "Compra e Venda de Pontos",
    "Lancamentos e Analises": "Lançamentos e Análises",
    "Bonus de Adesao": "Bônus de Adesão",
    "Anuidade e Isencao": "Anuidade e Isenção",
    "Aprovacao e Renda": "Aprovação e Renda",
    "Programas Hoteleiros": "Programas Hoteleiros",
    "Hospedagem com Pontos": "Hospedagem com Pontos",
    "Resorts e Experiencias": "Resorts e Experiências",
    "Destinos e Guias": "Destinos e Guias",
    "Promocoes de Hospedagem": "Promoções de Hospedagem",
    "Passagens Aereas": "Passagens Aéreas",
    "Cartoes e Cashback": "Cartões e Cashback",
    "Ofertas Relampago": "Ofertas Relâmpago",
}

MOJIBAKE_REPLACEMENTS = {
    "Ã¡": "á",
    "Ã¢": "â",
    "Ã£": "ã",
    "Ã©": "é",
    "Ãª": "ê",
    "Ã­": "í",
    "Ã³": "ó",
    "Ã´": "ô",
    "Ãµ": "õ",
    "Ãº": "ú",
    "Ã§": "ç",
    "Ã ": "à",
    "Â°": "°",
    "â€¢": "•",
    "â€“": "–",
    "â€”": "—",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
}

WORD_REPLACEMENTS = (
    (r"\bRedacao\b", "Redação"),
    (r"\bnoticias\b", "notícias"),
    (r"\bnoticia\b", "notícia"),
    (r"\bpromocoes\b", "promoções"),
    (r"\bpromocao\b", "promoção"),
    (r"\bcartoes\b", "cartões"),
    (r"\bcredito\b", "crédito"),
    (r"\bhoteis\b", "hotéis"),
    (r"\btransferencias\b", "transferências"),
    (r"\bbonus\b", "bônus"),
    (r"\barea\b", "área"),
    (r"\bcomentarios\b", "comentários"),
)


def _to_local(value):
    if isinstance(value, datetime):
        try:
            return timezone.localtime(value)
        except Exception:
            return value
    return value


def _repair_portuguese_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text in DISPLAY_LABELS:
        return DISPLAY_LABELS[text]
    for broken, fixed in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(broken, fixed)
    for pattern, replacement in WORD_REPLACEMENTS:
        def _replace(match):
            original = match.group(0)
            if original.isupper():
                return replacement.upper()
            if original[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        text = re.sub(pattern, _replace, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@register.filter
def br_date_long(value):
    value = _to_local(value)
    if not isinstance(value, (datetime, date)):
        return ""
    month = MONTHS_PT_BR.get(value.month, "")
    return f"{value.day:02d} de {month} de {value.year}"


@register.filter
def br_datetime_short(value):
    value = _to_local(value)
    if not isinstance(value, datetime):
        return ""
    month = MONTHS_PT_BR.get(value.month, "")
    return f"{value.day:02d} de {month} de {value.year}, {value:%H:%M}"


@register.filter
def portal_text(value):
    return _repair_portuguese_text(value)
