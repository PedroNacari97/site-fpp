import re
from datetime import date, datetime

from django import template
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe


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
    "Viagens": "Viagens",
    "Viagem": "Viagem",
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
    "Destinos e Roteiros": "Destinos e Roteiros",
    "Passagens e Voos": "Passagens e Voos",
    "Dicas de Viagem": "Dicas de Viagem",
    "Cruzeiros e Pacotes": "Cruzeiros e Pacotes",
    "Promocoes de Hospedagem": "Promoções de Hospedagem",
    "Passagens Aereas": "Passagens Aéreas",
    "Cartoes e Cashback": "Cartões e Cashback",
    "Ofertas Relampago": "Ofertas Relâmpago",
}

MOJIBAKE_REPLACEMENTS = {
    "ÃƒÂ¡": "á",
    "ÃƒÂ¢": "â",
    "ÃƒÂ£": "ã",
    "ÃƒÂ©": "é",
    "ÃƒÂª": "ê",
    "ÃƒÂ­": "í",
    "ÃƒÂ³": "ó",
    "ÃƒÂ´": "ô",
    "ÃƒÂµ": "õ",
    "ÃƒÂº": "ú",
    "ÃƒÂ§": "ç",
    "Ãƒ ": "à",
    "Ã‚Â°": "°",
    "Ã¢â‚¬Â¢": "•",
    "Ã¢â‚¬â€œ": "–",
    "Ã¢â‚¬â€": "—",
    "Ã¢â‚¬â„¢": "'",
    "Ã¢â‚¬Å“": '"',
    "Ã¢â‚¬Â": '"',
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


def repair_portuguese_text(value):
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
    return re.sub(r"\s+", " ", text).strip()


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
    return repair_portuguese_text(value)


def _markdown_to_html(text: str) -> str:
    """Converte markdown simples (negrito, links) para HTML seguro."""
    # Converte **texto** e *texto* para <strong>
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong>{escape(m.group(1))}</strong>", text)
    text = re.sub(r"\*(.+?)\*", lambda m: f"<strong>{escape(m.group(1))}</strong>", text)
    # Converte [texto](url) para <a> com rel seguro
    def _link(m):
        label = escape(m.group(1))
        url = m.group(2).strip()
        if not url.startswith(("http://", "https://")):
            return escape(m.group(0))
        return f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, text)
    return text


@register.filter
def portal_content(value):
    """Renderiza conteúdo de notícia: converte markdown simples e aplica linebreaks com HTML seguro."""
    repaired = repair_portuguese_text(str(value or ""))
    paragraphs = re.split(r"\n{2,}", repaired)
    html_parts = []
    for para in paragraphs:
        lines = para.strip().split("\n")
        converted_lines = [_markdown_to_html(line.strip()) for line in lines if line.strip()]
        if converted_lines:
            html_parts.append("<p>" + "<br>".join(converted_lines) + "</p>")
    return mark_safe("\n".join(html_parts))
