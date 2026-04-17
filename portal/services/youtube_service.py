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


def _parse_iso8601_duration(duration_str: str) -> str:
    """Converte duracao ISO 8601 (PT12M34S) para formato legivel (12:34).

    Exemplos:
        PT1H2M3S  -> 1:02:03
        PT12M34S  -> 12:34
        PT5M      -> 5:00
        PT30S     -> 0:30
    """
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


def search_youtube_videos(
    query: str,
    max_results: int = 3,
    language: str = "pt",
) -> list[dict]:
    """Busca videos no YouTube relacionados ao termo de pesquisa.

    Args:
        query: Termo de busca.
        max_results: Numero maximo de resultados (padrao 3).
        language: Idioma da busca (padrao 'pt').

    Returns:
        Lista de dicts com id, title, thumbnail, channel, duration, url.
    """
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY nao configurada, retornando mock")
        return _mock_youtube_results(query, max_results)

    try:
        # 1. Busca IDs dos videos
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

        # 2. Busca detalhes (duracao) dos videos
        details_params = {
            "part": "contentDetails,snippet",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY,
        }
        details_resp = requests.get(YOUTUBE_VIDEOS_URL, params=details_params, timeout=10)
        details_resp.raise_for_status()
        details_data = details_resp.json()

        videos = []
        for item in details_data.get("items", []):
            video_id = item["id"]
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            duration_raw = content_details.get("duration", "PT0S")

            videos.append({
                "id": video_id,
                "title": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "channel": snippet.get("channelTitle", ""),
                "duration": _parse_iso8601_duration(duration_raw),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })

        return videos

    except requests.RequestException as exc:
        logger.error("Erro ao buscar videos no YouTube: %s", exc)
        return _mock_youtube_results(query, max_results)


def _mock_youtube_results(query: str, max_results: int) -> list[dict]:
    """Retorna dados mock para desenvolvimento sem API key."""
    mock_videos = [
        {
            "id": "mock_video_1",
            "title": f"Como aproveitar {query} - Guia Completo",
            "thumbnail": "https://via.placeholder.com/480x360.png?text=Video+1",
            "channel": "NC Fly",
            "duration": "12:34",
            "url": "https://www.youtube.com/watch?v=mock_video_1",
        },
        {
            "id": "mock_video_2",
            "title": f"Tudo sobre {query} em 2024",
            "thumbnail": "https://via.placeholder.com/480x360.png?text=Video+2",
            "channel": "Milhas & Pontos",
            "duration": "8:15",
            "url": "https://www.youtube.com/watch?v=mock_video_2",
        },
        {
            "id": "mock_video_3",
            "title": f"{query}: dicas que ninguem te conta",
            "thumbnail": "https://via.placeholder.com/480x360.png?text=Video+3",
            "channel": "Viajando com Milhas",
            "duration": "15:42",
            "url": "https://www.youtube.com/watch?v=mock_video_3",
        },
    ]
    return mock_videos[:max_results]
