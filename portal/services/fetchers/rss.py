from __future__ import annotations

from datetime import datetime
import email.utils
import xml.etree.ElementTree as ET

from .base import FetchedEntry, extract_article_text, extract_image_from_html, extract_title_from_html, fetch_url, normalize_whitespace


class RssFetcher:
    def list_entries(self, source) -> list[FetchedEntry]:
        xml_text = fetch_url(source.url, headers=source.headers_json)
        root = ET.fromstring(xml_text)
        entries: list[FetchedEntry] = []
        for item in root.findall(".//item"):
            title = normalize_whitespace("".join(item.findtext("title", default="")))
            link = normalize_whitespace(item.findtext("link", default=""))
            description = normalize_whitespace(item.findtext("description", default=""))
            pub_date_raw = normalize_whitespace(item.findtext("pubDate", default=""))
            published_at = None
            if pub_date_raw:
                try:
                    published_at = email.utils.parsedate_to_datetime(pub_date_raw)
                except Exception:
                    published_at = None
            if not link:
                continue
            entries.append(
                FetchedEntry(
                    url=link,
                    title=title,
                    summary=description,
                    published_at=published_at,
                )
            )
        return entries

    def fetch_article(self, source, entry: FetchedEntry) -> FetchedEntry:
        html = fetch_url(entry.url, headers=source.headers_json)
        return FetchedEntry(
            url=entry.url,
            title=entry.title or extract_title_from_html(html),
            summary=entry.summary,
            published_at=entry.published_at,
            image_url=extract_image_from_html(html),
            html=html,
            text=extract_article_text(html),
        )

