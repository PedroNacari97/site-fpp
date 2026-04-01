from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
import re
import unicodedata

from portal.models import NoticiaPublicada


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


def normalize_story_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def tokenize_story_text(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalize_story_text(value))
        if token not in STOPWORDS
    ]


def build_story_fingerprint(title: str, summary: str = "", category: str = "", topic: str = "") -> str:
    title_tokens = tokenize_story_text(title)[:10]
    summary_tokens = tokenize_story_text(summary)[:12]
    combined_tokens = sorted(set(title_tokens + summary_tokens))[:18]
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


def find_duplicate_news(title: str, summary: str, category: str, topic: str, *, exclude_pk: int | None = None) -> NoticiaPublicada | None:
    fingerprint = build_story_fingerprint(title, summary, category, topic)
    normalized_title = normalize_story_text(title)
    candidate_tokens = set(tokenize_story_text(f"{title} {summary}"))

    queryset = (
        NoticiaPublicada.objects.exclude(status="archived")
        .exclude(pk=exclude_pk)
        .order_by("-publicada_em")[:300]
    )

    for existing in queryset:
        existing_fingerprint = (existing.metadata_json or {}).get("story_fingerprint") or build_story_fingerprint(
            existing.titulo,
            existing.resumo,
            existing.categoria,
            existing.topico,
        )
        if existing_fingerprint == fingerprint:
            return existing

        existing_title = normalize_story_text(existing.titulo)
        title_similarity = SequenceMatcher(None, normalized_title, existing_title).ratio()
        existing_tokens = set(tokenize_story_text(f"{existing.titulo} {existing.resumo}"))
        overlap = _token_overlap_ratio(candidate_tokens, existing_tokens)
        same_category = normalize_story_text(existing.categoria) == normalize_story_text(category)

        if title_similarity >= 0.93 and overlap >= 0.45:
            return existing
        if same_category and title_similarity >= 0.82 and overlap >= 0.68:
            return existing
        if same_category and overlap >= 0.68 and title_similarity >= 0.58:
            return existing

    return None


def append_source_reference(metadata: dict | None, *, source_name: str, article_url: str, title: str = "") -> dict:
    payload = dict(metadata or {})
    references = payload.setdefault("source_references", [])
    already_exists = any(
        isinstance(item, dict) and item.get("url") == article_url
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
    return payload
