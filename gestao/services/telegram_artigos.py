import json
import logging
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.utils import timezone

logger = logging.getLogger(__name__)

_ARTIGOS_BOT_TOKEN = os.environ.get("TELEGRAM_ARTIGOS_BOT_TOKEN", "")
_LAST_UPDATE_ID_KEY = "telegram_artigos_last_update_id"

ARTIGO_MIN_CHARS = 200


def _api_url(method):
    if not _ARTIGOS_BOT_TOKEN:
        raise ValueError("TELEGRAM_ARTIGOS_BOT_TOKEN não configurado.")
    return f"https://api.telegram.org/bot{_ARTIGOS_BOT_TOKEN}/{method}"


def telegram_artigos_send_message(chat_id, text):
    if not chat_id or not _ARTIGOS_BOT_TOKEN:
        return
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = Request(_api_url("sendMessage"), data=payload, headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=10)
    except URLError as exc:
        logger.warning("telegram_artigos_send_message: falha ao enviar mensagem: %s", exc)


def telegram_artigos_get_updates(limit=20, timeout=0, offset=None):
    params = f"limit={limit}&timeout={timeout}&allowed_updates=%5B%22message%22%2C%22channel_post%22%5D"
    if offset is not None:
        params += f"&offset={offset}"
    req = Request(f"{_api_url('getUpdates')}?{params}")
    try:
        with urlopen(req, timeout=timeout + 15) as resp:
            data = json.loads(resp.read())
    except URLError as exc:
        raise RuntimeError(f"Falha ao buscar updates do Telegram: {exc}") from exc
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API retornou erro: {data}")
    return data.get("result", [])


def process_telegram_artigos_update(update):
    """
    Processa um update do bot de artigos.
    Retorna (update_id, outcome, meta).
    Outcomes: 'published' | 'text_too_short' | 'ignored_empty' | 'processing_error'
    """
    update_id = update.get("update_id")
    message = update.get("message") or update.get("channel_post") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or message.get("caption") or "").strip()

    if not text:
        return update_id, "ignored_empty", {"chat_id": chat_id, "message": None}

    if len(text) < ARTIGO_MIN_CHARS:
        return update_id, "text_too_short", {
            "chat_id": chat_id,
            "message": f"Texto muito curto ({len(text)} caracteres). Envie pelo menos {ARTIGO_MIN_CHARS} caracteres para processar como artigo.",
        }

    try:
        from portal.services.ai_pipeline import build_news_draft
        from portal.models import NoticiaPublicada

        raw_article = {
            "texto_base": text,
            "titulo_extraido": "",
            "resumo_base": "",
            "categoria_padrao": "",
            "url_original": "",
            "data_publicacao_original": "",
            "outbound_links": [],
            "imagem_url": "",
        }
        draft = build_news_draft("telegram_artigos", raw_article)

        noticia = NoticiaPublicada(
            titulo=draft.titulo,
            resumo=draft.resumo,
            conteudo=draft.conteudo,
            categoria="Artigos",
            topico=draft.topico,
            tags_json=draft.tags,
            imagem_url=draft.imagem_url,
            imagem_ilustrativa=draft.imagem_ilustrativa,
            url_fonte="",
            status="published",
            confianca=draft.confianca,
            metadata_json={
                **(draft.metadata or {}),
                "origem": "telegram_artigos",
                "seo_title": draft.seo_title,
                "meta_description": draft.meta_description,
                "cta_url": draft.cta_url,
                "cta_label": draft.cta_label,
                "imagem_prompt": draft.imagem_prompt,
            },
        )
        noticia.save()

        base_url = os.environ.get("SITE_BASE_URL", "https://ncfly.com.br").rstrip("/")
        artigo_url = f"{base_url}{noticia.get_absolute_url()}"

        mensagem = (
            f"Artigo publicado!\n"
            f"Titulo: {noticia.titulo}\n"
            f"Categoria: {noticia.categoria}\n"
            f"Confianca: {int((noticia.confianca or 0) * 100)}%\n"
            f"Link: {artigo_url}"
        )
        return update_id, "published", {"chat_id": chat_id, "message": mensagem, "noticia_id": noticia.id}

    except Exception as exc:
        logger.exception("telegram_artigos: erro ao processar artigo (update_id=%s)", update_id)
        return update_id, "processing_error", {
            "chat_id": chat_id,
            "message": f"Erro ao processar o artigo: {exc}",
        }
