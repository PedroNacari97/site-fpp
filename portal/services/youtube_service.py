"""Integracao com YouTube Data API v3.

Busca videos relacionados a um termo de pesquisa para embutir
em artigos do portal.

Uso:
    from portal.services.youtube_service import search_youtube_videos

    videos = search_youtube_videos("milhas smiles", max_results=3)
"""
from __future__ import annotations

import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|v/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(value: str) -> str | None:
    """Extrai o ID de 11 chars de uma URL de YouTube ou retorna o valor se ja for ID."""
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    match = _VIDEO_ID_RE.search(value)
    return match.group(1) if match else None


def _parse_iso8601_duration(duration_str: str) -> str:
    """Converte duracao ISO 8601 (PT12M34S) para formato legivel (12:34)."""
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration_str or "",
    )
    if not match:
        return "0:00"

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _video_dict(item: dict, termo_busca: str = "") -> dict:
    """Monta dict padronizado com chaves alinhadas ao model ArtigoVideoYoutube."""
    video_id = item.get("id") or ""
    snippet = item.get("snippet", {}) or {}
    content_details = item.get("contentDetails", {}) or {}
    statistics = item.get("statistics", {}) or {}
    thumbnails = snippet.get("thumbnails", {}) or {}
    thumb = (
        thumbnails.get("high", {}).get("url")
        or thumbnails.get("medium", {}).get("url")
        or thumbnails.get("default", {}).get("url")
        or ""
    )
    try:
        views = int(statistics.get("viewCount") or 0)
    except (TypeError, ValueError):
        views = 0
    return {
        "video_id": video_id,
        "titulo": snippet.get("title", "") or "",
        "descricao": snippet.get("description", "") or "",
        "thumbnail_url": thumb,
        "canal": snippet.get("channelTitle", "") or "",
        "duracao": _parse_iso8601_duration(content_details.get("duration", "PT0S")),
        "visualizacoes": views,
        "termo_busca": termo_busca,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def fetch_videos_by_ids(video_ids: list[str], termo_busca: str = "") -> list[dict]:
    """Busca metadados (titulo, canal, duracao, viewcount) para IDs diretos."""
    clean_ids = [v for v in (extract_video_id(i) for i in video_ids) if v]
    if not clean_ids:
        return []
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY nao configurada, retornando mock")
        return [
            _video_dict({"id": vid, "snippet": {"title": f"Video {vid}"}}, termo_busca)
            for vid in clean_ids
        ]
    try:
        resp = requests.get(
            YOUTUBE_VIDEOS_URL,
            params={
                "part": "contentDetails,snippet,statistics",
                "id": ",".join(clean_ids),
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return [_video_dict(item, termo_busca) for item in resp.json().get("items", [])]
    except requests.RequestException as exc:
        logger.error("Erro ao buscar videos por id no YouTube: %s", exc)
        return []


def search_youtube_videos(
    query: str,
    max_results: int = 3,
    language: str = "pt",
) -> list[dict]:
    """Busca videos no YouTube relacionados ao termo de pesquisa.

    Returns:
        Lista de dicts com chaves: video_id, titulo, descricao, thumbnail_url,
        canal, duracao, visualizacoes, termo_busca, url.
    """
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY nao configurada, retornando mock")
        return _mock_youtube_results(query, max_results)

    try:
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "relevanceLanguage": language,
            "key": YOUTUBE_API_KEY,
        }
        search_resp = requests.get(YOUTUBE_SEARCH_URL, params=search_params, timeout=10)
        search_resp.raise_for_status()
        search_data = search_resp.json()

        video_ids = [
            item["id"]["videoId"]
            for item in search_data.get("items", [])
            if "videoId" in item.get("id", {})
        ]

        if not video_ids:
            return []

        return fetch_videos_by_ids(video_ids, termo_busca=query)

    except requests.RequestException as exc:
        logger.error("Erro ao buscar videos no YouTube: %s", exc)
        return _mock_youtube_results(query, max_results)


def _mock_youtube_results(query: str, max_results: int) -> list[dict]:
    """Retorna dados mock para desenvolvimento sem API key."""
    mock_videos = [
        {
            "video_id": "dQw4w9WgXcQ",
            "titulo": f"Como aproveitar {query} - Guia Completo",
            "descricao": "",
            "thumbnail_url": "https://via.placeholder.com/480x360.png?text=Video+1",
            "canal": "NC Fly",
            "duracao": "12:34",
            "visualizacoes": 0,
            "termo_busca": query,
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
        {
            "video_id": "9bZkp7q19f0",
            "titulo": f"Tudo sobre {query} em 2024",
            "descricao": "",
            "thumbnail_url": "https://via.placeholder.com/480x360.png?text=Video+2",
            "canal": "Milhas & Pontos",
            "duracao": "8:15",
            "visualizacoes": 0,
            "termo_busca": query,
            "url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
        },
        {
            "video_id": "kJQP7kiw5Fk",
            "titulo": f"{query}: dicas que ninguem te conta",
            "descricao": "",
            "thumbnail_url": "https://via.placeholder.com/480x360.png?text=Video+3",
            "canal": "Viajando com Milhas",
            "duracao": "15:42",
            "visualizacoes": 0,
            "termo_busca": query,
            "url": "https://www.youtube.com/watch?v=kJQP7kiw5Fk",
        },
    ]
    return mock_videos[:max_results]
