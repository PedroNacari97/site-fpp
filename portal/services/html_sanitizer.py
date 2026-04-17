"""Sanitizador de HTML usando apenas a stdlib.

Remove scripts, event handlers, tags e atributos inseguros.
Mantém apenas tags e atributos permitidos para conteudo editorial.

Uso:
    from portal.services.html_sanitizer import sanitize_article_html

    clean = sanitize_article_html(raw_html)
"""
from __future__ import annotations

import re
from html.parser import HTMLParser


ALLOWED_TAGS: frozenset[str] = frozenset({
    "a", "blockquote", "br", "div", "em", "figure", "figcaption",
    "h2", "h3", "h4", "hr", "img", "li", "ol", "p", "span",
    "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
})

ALLOWED_ATTRS: dict[str, list[str]] = {
    "*": ["class", "id"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}

VOID_TAGS: frozenset[str] = frozenset({
    "br", "hr", "img",
})

ALLOWED_PROTOCOLS: frozenset[str] = frozenset({
    "http", "https", "mailto",
})

_EVENT_HANDLER_RE = re.compile(r"^on\w+$", re.IGNORECASE)
_JAVASCRIPT_URI_RE = re.compile(r"^\s*javascript\s*:", re.IGNORECASE)
_DANGEROUS_DATA_URI_RE = re.compile(
    r"^\s*data\s*:[^,]*(?:text/html|application/xhtml|text/xml|image/svg)",
    re.IGNORECASE,
)


class _HTMLSanitizer(HTMLParser):
    """Parser que reconstroi HTML mantendo apenas tags/atributos permitidos."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        clean_attrs = self._clean_attrs(tag, attrs)
        attr_str = ""
        if clean_attrs:
            parts = []
            for k, v in clean_attrs:
                if v is None:
                    parts.append(f" {k}")
                else:
                    escaped = v.replace("&", "&amp;").replace('"', "&quot;")
                    parts.append(f' {k}="{escaped}"')
            attr_str = "".join(parts)
        if tag in VOID_TAGS:
            self._pieces.append(f"<{tag}{attr_str} />")
        else:
            self._pieces.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self._pieces.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        escaped = (
            data.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        self._pieces.append(escaped)

    def _clean_attrs(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> list[tuple[str, str | None]]:
        """Filtra atributos permitidos e remove event handlers / URIs perigosos."""
        allowed_for_tag = set(ALLOWED_ATTRS.get(tag, []))
        allowed_global = set(ALLOWED_ATTRS.get("*", []))
        allowed = allowed_for_tag | allowed_global

        clean: list[tuple[str, str | None]] = []
        for name, value in attrs:
            name = name.lower()

            # Bloqueia event handlers (onclick, onload, etc.)
            if _EVENT_HANDLER_RE.match(name):
                continue

            if name not in allowed:
                continue

            # Valida URLs em href e src
            if name in ("href", "src") and value is not None:
                val = value.strip()
                if _JAVASCRIPT_URI_RE.match(val):
                    continue
                if _DANGEROUS_DATA_URI_RE.match(val):
                    continue
                # Verifica protocolo
                if ":" in val.split("?", 1)[0].split("#", 1)[0]:
                    protocol = val.split(":", 1)[0].strip().lower()
                    if protocol not in ALLOWED_PROTOCOLS:
                        continue

            clean.append((name, value))
        return clean

    def get_output(self) -> str:
        return "".join(self._pieces)


def sanitize_article_html(html_content: str) -> str:
    """Sanitiza HTML de artigo, removendo tags e atributos inseguros.

    Args:
        html_content: HTML bruto a ser sanitizado.

    Returns:
        HTML limpo contendo apenas tags e atributos permitidos.
    """
    if not html_content:
        return ""
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(html_content)
    return sanitizer.get_output()
