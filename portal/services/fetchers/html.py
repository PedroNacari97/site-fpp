from __future__ import annotations

from collections import deque
import re
from urllib.parse import urlparse

from .base import (
    BaseFetcher,
    FetchedEntry,
    extract_article_text,
    extract_relevant_outbound_links,
    extract_image_from_html,
    extract_meta_content,
    extract_published_datetime,
    extract_title_from_html,
    fetch_url,
    is_same_domain,
    normalize_url,
    normalize_whitespace,
    strip_html,
)


class HtmlFetcher(BaseFetcher):
    anchor_pattern = re.compile(
        r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<text>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    blocked_text_prefixes = (
        "ver ",
        "filtrar",
        "home",
        "contato",
        "sobre",
        "buscar",
        "assine",
        "cadastre",
        "login",
    )

    blocked_url_tokens = (
        "/tag/",
        "/categoria/",
        "/category/",
        "/author/",
        "/wp-content/",
        "/feed/",
        "/page/",
        "#respond",
    )

    crawl_blocked_url_tokens = (
        "/wp-content/",
        "/wp-json/",
        "/feed/",
        "/author/",
        "#respond",
    )

    crawl_page_limit = 24
    sitemap_url_limit = 160
    sitemap_depth_limit = 6
    anchor_context_radius = 180

    def should_skip_url(self, source, absolute_url: str, text: str) -> bool:
        lower_url = absolute_url.lower()
        lower_text = text.lower()
        if any(token in lower_url for token in self.blocked_url_tokens):
            return True
        if any(lower_text.startswith(prefix) for prefix in self.blocked_text_prefixes):
            return True
        if len(text.split()) < 4:
            return True
        return False

    def should_queue_url(self, source, absolute_url: str, text: str = "") -> bool:
        lower_url = absolute_url.lower()
        path = urlparse(absolute_url).path.lower()
        if any(token in lower_url for token in self.crawl_blocked_url_tokens):
            return False
        if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".xml", ".zip")):
            return False
        if re.search(r"/(?:wp-admin|login|contato|conta|cadastro|termos|privacidade)(?:/|$)", path):
            return False
        if len(path.strip("/").split("/")) > 6:
            return False
        return True

    def looks_like_article_url(self, absolute_url: str) -> bool:
        lower_url = absolute_url.lower()
        path = urlparse(absolute_url).path.lower().strip("/")
        if not path:
            return False
        if any(token in lower_url for token in self.blocked_url_tokens):
            return False
        if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".xml", ".zip")):
            return False
        if re.search(r"/page/\d+/?$", f"/{path}/"):
            return False
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 2:
            return True
        slug = segments[-1] if segments else ""
        if len(slug.split("-")) >= 3:
            return True
        if any(char.isdigit() for char in slug) and len(slug) >= 8:
            return True
        return False

    def score_sitemap_article(self, absolute_url: str) -> int:
        score = 5
        lower_url = absolute_url.lower()
        if absolute_url.endswith(".html"):
            score += 4
        if re.search(r"/\d{4}/", lower_url):
            score += 3
        if len(urlparse(absolute_url).path.strip("/").split("/")) >= 2:
            score += 2
        return score

    def _extract_urls_from_xml(self, xml_text: str) -> list[str]:
        return [
            normalize_url("", match.group(1).strip())
            for match in re.finditer(r"<loc>\s*(.*?)\s*</loc>", xml_text or "", re.IGNORECASE | re.DOTALL)
            if match.group(1).strip()
        ]

    def discover_sitemap_urls(self, source) -> list[str]:
        discovered: list[str] = []
        seen: set[str] = set()
        sitemap_queue: deque[str] = deque()
        candidate_sitemaps = [
            normalize_url(source.url, "/robots.txt"),
            normalize_url(source.url, "/sitemap.xml"),
            normalize_url(source.url, "/sitemap_index.xml"),
        ]

        for candidate in candidate_sitemaps:
            if candidate not in seen:
                seen.add(candidate)
                sitemap_queue.append(candidate)

        processed_sitemaps = 0
        while sitemap_queue and processed_sitemaps < self.sitemap_depth_limit and len(discovered) < self.sitemap_url_limit:
            sitemap_url = sitemap_queue.popleft()
            processed_sitemaps += 1
            try:
                payload = fetch_url(sitemap_url, headers=source.headers_json)
            except Exception:
                continue

            if sitemap_url.endswith("/robots.txt") or "/robots.txt" in sitemap_url:
                for line in payload.splitlines():
                    if line.lower().startswith("sitemap:"):
                        candidate = line.split(":", 1)[1].strip()
                        if candidate and candidate not in seen:
                            seen.add(candidate)
                            sitemap_queue.append(candidate)
                continue

            urls = self._extract_urls_from_xml(payload)
            if "<sitemapindex" in payload.lower():
                for url in urls:
                    if url not in seen and is_same_domain(source.url, url):
                        seen.add(url)
                        sitemap_queue.append(url)
                continue

            for url in urls:
                if not is_same_domain(source.url, url):
                    continue
                if url not in discovered:
                    discovered.append(url)
                if len(discovered) >= self.sitemap_url_limit:
                    break
        return discovered

    def get_seed_urls(self, source) -> list[str]:
        sitemap_urls = self.discover_sitemap_urls(source)
        queue_candidates = [source.url]
        queue_candidates.extend(url for url in sitemap_urls if self.should_queue_url(source, url))
        ordered: list[str] = []
        seen: set[str] = set()
        for url in queue_candidates:
            if url and url not in seen:
                seen.add(url)
                ordered.append(url)
        return ordered

    def _build_entry_title_from_url(self, absolute_url: str) -> str:
        slug = urlparse(absolute_url).path.rstrip("/").split("/")[-1]
        slug = re.sub(r"[-_]+", " ", slug)
        return slug.strip().title()

    def score_entry(self, source, absolute_url: str, text: str, context: str) -> int:
        score = 0
        lower_url = absolute_url.lower()
        lower_text = text.lower()
        lower_context = context.lower()

        score += min(len(text.split()) // 3, 4)
        if len(text) >= 45:
            score += 2
        if absolute_url.endswith(".html"):
            score += 5
        if re.search(r"/\d{4}/|\d{2}[a-z]{3}\d{2}", lower_url):
            score += 3
        if any(token in lower_context for token in ("há ", "hora", "horas", "min", "publicado", "atualizado")):
            score += 3
        if any(token in lower_text for token in ("promo", "milhas", "cart", "hotel", "resort", "pontos")):
            score += 1
        return score

    def list_entries(self, source) -> list[FetchedEntry]:
        seen: set[str] = set()
        ranked_entries: list[tuple[int, int, FetchedEntry]] = []
        order = 0

        for sitemap_url in self.discover_sitemap_urls(source):
            if not self.looks_like_article_url(sitemap_url):
                continue
            if sitemap_url in seen:
                continue
            seen.add(sitemap_url)
            ranked_entries.append(
                (
                    self.score_sitemap_article(sitemap_url),
                    order,
                    FetchedEntry(url=sitemap_url, title=self._build_entry_title_from_url(sitemap_url)),
                )
            )
            order += 1

        queue: deque[str] = deque(self.get_seed_urls(source))
        visited_pages: set[str] = set()
        while queue and len(visited_pages) < self.crawl_page_limit:
            page_url = queue.popleft()
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = fetch_url(page_url, headers=source.headers_json)
            except Exception:
                continue

            for match in self.anchor_pattern.finditer(html):
                href = match.group("href").strip()
                text = strip_html(match.group("text"))
                absolute_url = normalize_url(page_url, href)
                if not absolute_url.startswith(("http://", "https://")):
                    continue
                if not is_same_domain(source.url, absolute_url):
                    continue

                if self.should_queue_url(source, absolute_url, text) and absolute_url not in visited_pages and absolute_url not in queue:
                    queue.append(absolute_url)

                if len(text) < 20:
                    continue
                if self.should_skip_url(source, absolute_url, text):
                    continue
                if absolute_url in seen:
                    continue
                if not self.looks_like_article_url(absolute_url):
                    continue
                context = html[max(0, match.start() - self.anchor_context_radius): match.end() + self.anchor_context_radius]
                score = self.score_entry(source, absolute_url, text, context)
                if score < 4:
                    continue
                seen.add(absolute_url)
                ranked_entries.append((score, order, FetchedEntry(url=absolute_url, title=text)))
                order += 1
        ranked_entries.sort(key=lambda item: (-item[0], item[1]))
        return [entry for _, _, entry in ranked_entries[: max(20, self.crawl_page_limit * 2)]]

    def fetch_article(self, source, entry: FetchedEntry) -> FetchedEntry:
        html = fetch_url(entry.url, headers=source.headers_json)
        summary = extract_meta_content(html, "description") or extract_meta_content(html, "og:description")
        image_url = extract_image_from_html(html)
        metadata = dict(entry.metadata or {})
        metadata["outbound_links"] = extract_relevant_outbound_links(html, entry.url)
        return FetchedEntry(
            url=entry.url,
            title=entry.title or extract_title_from_html(html),
            summary=normalize_whitespace(summary),
            published_at=extract_published_datetime(html),
            image_url=normalize_url(entry.url, image_url) if image_url else "",
            html=html,
            text=extract_article_text(html),
            metadata=metadata,
        )


class PassageiroDePrimeiraFetcher(HtmlFetcher):
    def should_skip_url(self, source, absolute_url: str, text: str) -> bool:
        if super().should_skip_url(source, absolute_url, text):
            return True
        return "/categorias/" in absolute_url.lower()


class MelhoresCartoesFetcher(HtmlFetcher):
    def score_entry(self, source, absolute_url: str, text: str, context: str) -> int:
        score = super().score_entry(source, absolute_url, text, context)
        if absolute_url.lower().endswith(".html"):
            score += 3
        return score
