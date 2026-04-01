from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass
class FetchedEntry:
    url: str
    title: str = ""
    published_at: datetime | None = None
    image_url: str = ""
    summary: str = ""
    html: str = ""
    text: str = ""
    metadata: dict = field(default_factory=dict)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())

    def get_text(self):
        return " ".join(self.parts)


NOISE_TEXT_MARKERS = (
    "filtrar por",
    "ver todos",
    "publicidade",
    "alertas do pp",
    "deixe um comentario",
    "deixe um comentário",
    "baixe nosso app",
    "cadastre-se",
    "cadastre se",
    "newsletter",
    "compartilhe",
    "noticias relacionadas",
    "notícias relacionadas",
    "sobre o autor",
    "termos de uso",
    "politica de privacidade",
    "política de privacidade",
    "ultimas noticias",
    "últimas notícias",
)

STOP_TEXT_MARKERS = (
    "deixe um comentario",
    "deixe um comentário",
    "noticias relacionadas",
    "notícias relacionadas",
    "sobre o autor",
    "baixe nosso app",
    "cadastre-se",
    "cadastre se",
)

OUTBOUND_LINK_BLOCKED_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "t.me",
    "telegram.me",
    "wa.me",
    "whatsapp.com",
    "pinterest.com",
)


def fetch_url(url: str, headers: dict | None = None, timeout: int = 20) -> str:
    merged_headers = {
        "User-Agent": "NCFlyBot/1.0 (+https://ncfly.local)",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    merged_headers.update(headers or {})
    request = Request(url, headers=merged_headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def normalize_url(base_url: str, raw_url: str) -> str:
    return urljoin(base_url, raw_url.split("#", 1)[0].strip())


def strip_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    return normalize_whitespace(unescape(parser.get_text()))


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _strip_non_content_blocks(html: str) -> str:
    cleaned = html or ""
    patterns = [
        r"<script\b[^>]*>.*?</script>",
        r"<style\b[^>]*>.*?</style>",
        r"<noscript\b[^>]*>.*?</noscript>",
        r"<svg\b[^>]*>.*?</svg>",
        r"<form\b[^>]*>.*?</form>",
        r"<select\b[^>]*>.*?</select>",
        r"<nav\b[^>]*>.*?</nav>",
        r"<footer\b[^>]*>.*?</footer>",
        r"<aside\b[^>]*>.*?</aside>",
        r"<header\b[^>]*>.*?</header>",
        r"<!--.*?-->",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def _extract_article_body_from_json_ld(html: str) -> str:
    article_types = {"article", "newsarticle", "blogposting", "report"}
    bodies: list[str] = []
    for item in extract_json_ld(html):
        item_type = item.get("@type")
        if isinstance(item_type, list):
            normalized_types = {normalize_whitespace(str(value)).lower() for value in item_type}
        else:
            normalized_types = {normalize_whitespace(str(item_type)).lower()} if item_type else set()
        if normalized_types and not (normalized_types & article_types):
            continue
        for key in ("articleBody", "description"):
            value = item.get(key)
            if value:
                bodies.append(normalize_whitespace(str(value)))
    return max((body for body in bodies if len(body) >= 280), key=len, default="")


def _is_noise_paragraph(text: str) -> bool:
    normalized = normalize_whitespace(text).lower()
    if len(normalized) < 35:
        return True
    if any(marker in normalized for marker in NOISE_TEXT_MARKERS):
        return True
    if normalized.count("•") >= 3 or normalized.count("|") >= 3:
        return True
    if len(set(normalized.split())) <= 4 and len(normalized.split()) <= 8:
        return True
    return False


def _clean_article_text(text: str) -> str:
    lines = []
    seen = set()
    for raw_part in re.split(r"(?:\n{2,}|(?<=[\.\!\?])\s{2,})", text or ""):
        part = normalize_whitespace(raw_part)
        if not part or _is_noise_paragraph(part):
            continue
        lowered = part.lower()
        if lowered in seen:
            continue
        if any(marker in lowered for marker in STOP_TEXT_MARKERS):
            break
        seen.add(lowered)
        lines.append(part)
    return "\n\n".join(lines)


def _extract_paragraph_text(html: str) -> str:
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", html or "", re.IGNORECASE | re.DOTALL)
    pieces: list[str] = []
    for paragraph in paragraphs:
        text = strip_html(paragraph)
        if text and not _is_noise_paragraph(text):
            pieces.append(text)
    return _clean_article_text("\n\n".join(pieces))


def extract_meta_content(html: str, property_name: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(property_name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+name=["\']{re.escape(property_name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(property_name)}["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(property_name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            return normalize_whitespace(unescape(match.group(1)))
    return ""


def extract_title_from_html(html: str) -> str:
    for key in ("og:title", "twitter:title"):
        title = extract_meta_content(html, key)
        if title:
            return title
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return normalize_whitespace(strip_html(match.group(1))) if match else ""


def extract_image_from_html(html: str) -> str:
    for key in ("og:image", "twitter:image"):
        image_url = extract_meta_content(html, key)
        if image_url:
            return image_url
    match = re.search(r'<img[^>]+src=["\'](.*?)["\']', html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_article_text(html: str) -> str:
    json_ld_text = _clean_article_text(_extract_article_body_from_json_ld(html))
    if len(json_ld_text) >= 400:
        return json_ld_text

    cleaned_html = _strip_non_content_blocks(html)
    paragraph_text = _extract_paragraph_text(cleaned_html)
    if len(paragraph_text) >= 120:
        return paragraph_text

    candidates = [
        re.search(r"<article\b[^>]*>(.*?)</article>", cleaned_html, re.IGNORECASE | re.DOTALL),
        re.search(r"<main\b[^>]*>(.*?)</main>", cleaned_html, re.IGNORECASE | re.DOTALL),
        re.search(r"<body\b[^>]*>(.*?)</body>", cleaned_html, re.IGNORECASE | re.DOTALL),
    ]
    for candidate in candidates:
        if candidate and candidate.group(1):
            text = _extract_paragraph_text(candidate.group(1)) or _clean_article_text(strip_html(candidate.group(1)))
            if len(text) > 120:
                return text
    return _clean_article_text(strip_html(cleaned_html))


def extract_json_ld(html: str) -> Iterable[dict]:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
        elif isinstance(data, dict):
            yield data


def extract_published_datetime(html: str) -> datetime | None:
    for key in ("article:published_time", "og:published_time", "datePublished"):
        value = extract_meta_content(html, key)
        if not value:
            for item in extract_json_ld(html):
                candidate = item.get(key)
                if candidate:
                    value = str(candidate)
                    break
        if not value:
            continue
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            continue
    return None


def is_same_domain(base_url: str, candidate_url: str) -> bool:
    try:
        base = urlparse(base_url).netloc
        candidate = urlparse(candidate_url).netloc
        return not candidate or candidate == base
    except Exception:
        return False


def extract_relevant_outbound_links(html: str, base_url: str, limit: int = 5) -> list[dict]:
    links: list[tuple[int, dict]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<text>.*?)</a>', html or "", re.IGNORECASE | re.DOTALL):
        href = (match.group("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute_url = normalize_url(base_url, href)
        if not absolute_url.startswith(("http://", "https://")):
            continue
        if is_same_domain(base_url, absolute_url):
            continue
        domain = urlparse(absolute_url).netloc.lower()
        if any(blocked in domain for blocked in OUTBOUND_LINK_BLOCKED_DOMAINS):
            continue

        anchor_text = strip_html(match.group("text"))[:120]
        if not anchor_text:
            continue
        key = absolute_url.lower()
        if key in seen:
            continue
        seen.add(key)

        lower_text = anchor_text.lower()
        lower_url = absolute_url.lower()
        score = 1
        if any(token in lower_text for token in ("aproveite", "oferta", "promocao", "promo", "comprar", "assinar", "cadastre", "clique", "ver oferta")):
            score += 5
        if any(token in lower_url for token in ("promo", "oferta", "sale", "deal", "comprar", "booking", "reserva", "subscribe")):
            score += 3
        if len(anchor_text.split()) >= 2:
            score += 1
        links.append(
            (
                score,
                {
                    "url": absolute_url,
                    "label": anchor_text,
                    "domain": domain,
                },
            )
        )

    links.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in links[:limit]]


class BaseFetcher:
    def list_entries(self, source) -> list[FetchedEntry]:
        raise NotImplementedError

    def fetch_article(self, source, entry: FetchedEntry) -> FetchedEntry:
        raise NotImplementedError
