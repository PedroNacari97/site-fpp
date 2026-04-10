from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from portal.models import NoticiaPublicada


STORY_FINGERPRINT_VERSION = 2

STOPWORDS = {
    "para",
    "com",
    "sem",
    "sobre",
    "entre",
    "ainda",
    "agora",
    "mais",
    "menos",
    "como",
    "onde",
    "quando",
    "porque",
    "passagens",
    "passagem",
    "milhas",
    "pontos",
    "noticia",
    "noticias",
    "portal",
    "ncfly",
}

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "source",
}

TRACKING_QUERY_PREFIXES = (
    "utm_",
)


def normalize_story_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_reference_url(url: str) -> str:
    raw_url = (url or "").strip()
    if not raw_url:
        return ""
    parts = urlsplit(raw_url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    normalized_path = re.sub(r"/+", "/", parts.path or "/").rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            normalized_path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def tokenize_story_text(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalize_story_text(value))
        if token not in STOPWORDS
    ]


def _trim_story_body(value: str, *, limit: int = 2400) -> str:
    return normalize_whitespace(value)[:limit]


def build_story_fingerprint(title: str, summary: str = "", category: str = "", topic: str = "", body: str = "") -> str:
    title_tokens = tokenize_story_text(title)[:12]
    summary_tokens = tokenize_story_text(summary)[:14]
    base_tokens = set(title_tokens + summary_tokens)
    body_tokens = [
        token
        for token in tokenize_story_text(_trim_story_body(body))
        if token not in base_tokens
    ][:18]
    combined_tokens = sorted(set(title_tokens + summary_tokens + body_tokens))[:26]
    base = "|".join(
        [
            normalize_story_text(category),
            normalize_story_text(topic),
            " ".join(combined_tokens),
        ]
    )
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _token_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _metadata_reference_urls(metadata: dict | None) -> set[str]:
    payload = metadata or {}
    urls: set[str] = set()

    for item in payload.get("source_references", []) or []:
        if isinstance(item, dict) and item.get("url"):
            normalized = normalize_reference_url(item["url"])
            if normalized:
                urls.add(normalized)

    offer_cta = payload.get("offer_cta") or {}
    if isinstance(offer_cta, dict) and offer_cta.get("url"):
        normalized = normalize_reference_url(offer_cta["url"])
        if normalized:
            urls.add(normalized)

    return urls


def _outbound_reference_urls(raw_metadata: dict | None) -> set[str]:
    urls: set[str] = set()
    for item in (raw_metadata or {}).get("outbound_links", []) or []:
        if isinstance(item, dict) and item.get("url"):
            normalized = normalize_reference_url(item["url"])
            if normalized:
                urls.add(normalized)
    return urls


def _existing_story_body(existing: NoticiaPublicada) -> str:
    if existing.materia_bruta_id and existing.materia_bruta and existing.materia_bruta.texto_base:
        return existing.materia_bruta.texto_base
    return existing.conteudo


def _existing_story_fingerprint(existing: NoticiaPublicada) -> str:
    metadata = existing.metadata_json or {}
    if metadata.get("story_fingerprint_version") == STORY_FINGERPRINT_VERSION and metadata.get("story_fingerprint"):
        return metadata["story_fingerprint"]
    return build_story_fingerprint(
        existing.titulo,
        existing.resumo,
        existing.categoria,
        existing.topico,
        _existing_story_body(existing),
    )


def find_duplicate_news(
    title: str,
    summary: str,
    category: str,
    topic: str,
    *,
    body: str = "",
    outbound_urls: list[str] | None = None,
    exclude_pk: int | None = None,
    source_url: str = "",
    manual_submission: bool = False,
) -> NoticiaPublicada | None:
    fingerprint = build_story_fingerprint(title, summary, category, topic, body)
    normalized_title = normalize_story_text(title)
    normalized_body = normalize_story_text(_trim_story_body(body))
    candidate_tokens = set(tokenize_story_text(f"{title} {summary} {_trim_story_body(body)}"))
    candidate_title_tokens = set(tokenize_story_text(title))
    candidate_outbound_urls = {
        normalized
        for normalized in (normalize_reference_url(url) for url in (outbound_urls or []))
        if normalized
    }
    normalized_source_url = normalize_reference_url(source_url)
    normalized_category = normalize_story_text(category)
    normalized_topic = normalize_story_text(topic)

    queryset = (
        NoticiaPublicada.objects.exclude(status="archived")
        .exclude(pk=exclude_pk)
        .select_related("materia_bruta")
        .order_by("-publicada_em")[:300]
    )

    for existing in queryset:
        existing_source_url = normalize_reference_url(
            (existing.materia_bruta.url_original if existing.materia_bruta_id and existing.materia_bruta else existing.url_fonte) or ""
        )
        if normalized_source_url and existing_source_url == normalized_source_url:
            return existing

        existing_fingerprint = _existing_story_fingerprint(existing)
        if existing_fingerprint == fingerprint:
            return existing

        existing_title = normalize_story_text(existing.titulo)
        existing_body = _existing_story_body(existing)
        existing_body_normalized = normalize_story_text(_trim_story_body(existing_body))
        title_similarity = SequenceMatcher(None, normalized_title, existing_title).ratio()
        body_similarity = (
            SequenceMatcher(None, normalized_body, existing_body_normalized).ratio()
            if normalized_body and existing_body_normalized
            else 0.0
        )
        existing_tokens = set(tokenize_story_text(f"{existing.titulo} {existing.resumo} {_trim_story_body(existing_body)}"))
        existing_title_tokens = set(tokenize_story_text(existing.titulo))
        overlap = _token_overlap_ratio(candidate_tokens, existing_tokens)
        title_token_overlap = _token_overlap_ratio(candidate_title_tokens, existing_title_tokens)
        same_category = normalize_story_text(existing.categoria) == normalized_category
        same_topic = normalized_topic and normalize_story_text(existing.topico) == normalized_topic

        existing_reference_urls = _metadata_reference_urls(existing.metadata_json)
        if existing.materia_bruta_id and existing.materia_bruta and existing.materia_bruta.metadata_json:
            existing_reference_urls |= _outbound_reference_urls(existing.materia_bruta.metadata_json)
        outbound_overlap = bool(candidate_outbound_urls & existing_reference_urls)

        if manual_submission:
            if outbound_overlap and (title_similarity >= 0.86 or body_similarity >= 0.8 or overlap >= 0.78):
                return existing
            if same_category and title_similarity >= 0.92 and overlap >= 0.68:
                return existing
            if same_category and same_topic and body_similarity >= 0.84 and overlap >= 0.7:
                return existing
            if title_token_overlap >= 0.85 and body_similarity >= 0.78:
                return existing
            continue

        if outbound_overlap and (same_category or same_topic or overlap >= 0.45):
            return existing

        if title_similarity >= 0.93 and overlap >= 0.45:
            return existing
        if same_category and title_similarity >= 0.82 and overlap >= 0.68:
            return existing
        if same_category and overlap >= 0.68 and title_similarity >= 0.58:
            return existing
        if same_category and same_topic and body_similarity >= 0.72 and overlap >= 0.56:
            return existing
        if same_category and title_token_overlap >= 0.6 and overlap >= 0.62:
            return existing

    return None


def append_source_reference(metadata: dict | None, *, source_name: str, article_url: str, title: str = "") -> dict:
    payload = dict(metadata or {})
    references = payload.setdefault("source_references", [])
    normalized_article_url = normalize_reference_url(article_url)
    already_exists = any(
        isinstance(item, dict) and normalize_reference_url(item.get("url", "")) == normalized_article_url
        for item in references
    )
    if not already_exists:
        references.append(
            {
                "source": source_name,
                "url": article_url,
                "title": title,
            }
        )
    payload["story_fingerprint_version"] = STORY_FINGERPRINT_VERSION
    return payload
