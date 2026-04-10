import hashlib
import json
import re

from django.conf import settings
from django.utils import timezone

from gestao.models import TelegramNoticiaEvento


TELEGRAM_NEWS_ALLOWED_UPDATE_TYPES = ["message", "channel_post"]
_NEWS_COMMAND_RE = re.compile(r"^atualizar\s*(\d+)?$", re.IGNORECASE)
_NEWS_URL_COMMAND_RE = re.compile(r"^(?:not[íi]cia|publicar|link)\s+(https?://\S+)\s*$", re.IGNORECASE)
_DIRECT_NEWS_URL_RE = re.compile(r"^(https?://\S+)\s*$", re.IGNORECASE)
_EMBEDDED_URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)
_MANUAL_NEWS_HINTS = (
    "promocode",
    "regra juridica",
    "regra jurídica",
    "data de venda",
    "data de viagem",
    "tipo de produto",
    "tipo de execução",
    "tipo de aplicacao",
    "tipo de aplicação",
    "% off",
    "anuidade gratis",
    "anuidade grátis",
)
_INVISIBLE_NEWS_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")


def get_telegram_noticias_config():
    allowed_chat_ids = set()
    for item in getattr(settings, "TELEGRAM_NEWS_ALLOWED_CHAT_IDS", []):
        cleaned = str(item).strip()
        if cleaned:
            allowed_chat_ids.add(cleaned)
    return {
        "token": getattr(settings, "TELEGRAM_NEWS_BOT_TOKEN", "").strip(),
        "secret": getattr(settings, "TELEGRAM_NEWS_WEBHOOK_SECRET", "").strip(),
        "allowed_chat_ids": allowed_chat_ids,
    }


def build_telegram_news_api_url(method_name):
    config = get_telegram_noticias_config()
    token = config["token"]
    if not token:
        raise ValueError("TELEGRAM_NEWS_BOT_TOKEN nao configurado.")
    return f"https://api.telegram.org/bot{token}/{method_name}"


def _sanitize_news_text(text):
    cleaned = text or ""
    for char in _INVISIBLE_NEWS_CHARS:
        cleaned = cleaned.replace(char, "")
    return cleaned.strip()


def _extract_message(update):
    message = update.get("channel_post") or update.get("message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = _sanitize_news_text(message.get("text") or message.get("caption") or "")
    remetente = (
        sender.get("username")
        or " ".join(part for part in [sender.get("first_name"), sender.get("last_name")] if part)
        or chat.get("title")
        or ""
    )
    return {
        "text": text,
        "chat_id": chat.get("id"),
        "chat_nome": chat.get("title") or chat.get("username") or "",
        "message_id": message.get("message_id"),
        "remetente": remetente.strip(),
    }


def _parse_news_command(text):
    match = _NEWS_COMMAND_RE.match((text or "").strip())
    if match:
        limit = int(match.group(1)) if match.group(1) else 10
        return max(1, min(limit, 50))
    return None


def _clean_submitted_url(url):
    return _sanitize_news_text(url).rstrip(").,;>")


def _strip_news_urls(text):
    return _EMBEDDED_URL_RE.sub(" ", text or "")


def parse_single_news_url_command(text):
    raw_text = (text or "").strip()
    if not raw_text:
        return None

    command_match = _NEWS_URL_COMMAND_RE.match(raw_text)
    if command_match:
        return _clean_submitted_url(command_match.group(1))

    direct_match = _DIRECT_NEWS_URL_RE.match(raw_text)
    if direct_match:
        return _clean_submitted_url(direct_match.group(1))

    if looks_like_manual_news_text(raw_text):
        return None

    embedded_match = _EMBEDDED_URL_RE.search(raw_text)
    if embedded_match:
        return _clean_submitted_url(embedded_match.group(1))

    return None


def looks_like_manual_news_text(text):
    raw_text = _sanitize_news_text(text)
    if len(raw_text) < 160:
        return False
    text_without_urls = _strip_news_urls(raw_text)
    lowered = text_without_urls.lower()
    score = sum(1 for hint in _MANUAL_NEWS_HINTS if hint in lowered)
    structured_fields = text_without_urls.count(":")
    multiline = "\n" in raw_text
    has_url = bool(_EMBEDDED_URL_RE.search(raw_text))
    return (
        score >= 2
        or (score >= 1 and len(text_without_urls.strip()) >= 220 and (structured_fields >= 2 or multiline))
        or (score >= 1 and has_url and len(text_without_urls.strip()) >= 140 and (structured_fields >= 1 or multiline))
    )


def _find_recent_duplicate(message_hash, chat_id):
    if not message_hash or chat_id in (None, ""):
        return None
    return (
        TelegramNoticiaEvento.objects.filter(mensagem_hash=message_hash, chat_id=chat_id)
        .exclude(status=TelegramNoticiaEvento.STATUS_ERRO)
        .order_by("-recebido_em")
        .first()
    )


def _build_result_message(result):
    noticia = result.get("noticia")
    outcome = result.get("outcome")
    noticia_url = f"https://www.ncfly.com.br{noticia.get_absolute_url()}" if noticia else ""
    titulo = noticia.titulo if noticia else ""

    if outcome == "duplicate_reference":
        return f"Encontrei uma noticia ja publicada para essa pauta.\n{titulo}\n{noticia_url}".strip()
    if outcome == "updated":
        return f"Noticia atualizada.\n{titulo}\n{noticia_url}".strip()
    if outcome == "draft":
        return f"Conteudo processado como rascunho.\n{titulo}".strip()
    if outcome == "already_published":
        return f"Essa noticia ja estava publicada.\n{titulo}\n{noticia_url}".strip()
    return f"Noticia publicada.\n{titulo}\n{noticia_url}".strip()


def _build_sync_batch_message(limit: int, processed: int, published: int, errors: list[str] | None = None) -> str:
    errors = errors or []
    lines = [
        "Atualizacao concluida.",
        f"Solicitadas: ate {limit} noticia(s).",
        f"Processadas: {processed}.",
        f"Publicadas: {published}.",
    ]
    if errors:
        lines.append(f"Erros: {len(errors)}.")
        lines.append(f"Primeiro erro: {errors[0][:220]}")
    elif published == 0:
        lines.append("Nenhuma noticia nova foi publicada nesta rodada.")
    return "\n".join(lines)


def process_telegram_news_update(update):
    from portal.services.news_sync_service import (
        sync_news_from_text,
        sync_news_from_url,
        sync_news_progressive,
    )
    from portal.views import invalidate_news_cache

    update_id = update.get("update_id")
    if update_id is None:
        raise ValueError("Update do Telegram sem update_id.")

    message = _extract_message(update)
    raw_text = _sanitize_news_text(message["text"])
    message_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else ""

    event, created = TelegramNoticiaEvento.objects.get_or_create(
        update_id=update_id,
        defaults={
            "chat_id": message["chat_id"],
            "message_id": message["message_id"],
            "chat_nome": message["chat_nome"],
            "remetente": message["remetente"],
            "mensagem_hash": message_hash,
            "texto_bruto": raw_text,
            "payload_json": update,
            "status": TelegramNoticiaEvento.STATUS_RECEBIDO,
        },
    )
    if not created:
        return event, "duplicate_update", {}

    config = get_telegram_noticias_config()
    chat_id = message["chat_id"]
    if config["allowed_chat_ids"] and str(chat_id) not in config["allowed_chat_ids"]:
        event.status = TelegramNoticiaEvento.STATUS_IGNORADO
        event.erro = "Chat nao autorizado para o bot de noticias."
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "ignored_chat", {}

    if not raw_text:
        event.status = TelegramNoticiaEvento.STATUS_IGNORADO
        event.erro = "Mensagem sem texto util para processar noticia."
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "ignored_empty", {}

    duplicate_event = _find_recent_duplicate(message_hash, chat_id)
    if duplicate_event and duplicate_event.id != event.id:
        event.status = TelegramNoticiaEvento.STATUS_IGNORADO
        event.erro = "Mensagem duplicada ja processada anteriormente."
        event.noticia = duplicate_event.noticia
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "noticia", "processado_em"])
        return event, "ignored_duplicate_message", {}

    try:
        news_limit = _parse_news_command(raw_text)
        if news_limit is not None:
            processed, published, errors = sync_news_progressive(limit=news_limit)
            invalidate_news_cache()
            event.status = TelegramNoticiaEvento.STATUS_PROCESSADO
            event.processado_em = timezone.now()
            event.save(update_fields=["status", "processado_em"])
            summary = _build_sync_batch_message(news_limit, processed, published, errors)
            return event, "sync_batch", {"message": summary}

        news_url = parse_single_news_url_command(raw_text)
        if news_url:
            result = sync_news_from_url(news_url, publish_drafts=True, refresh_published=True)
            invalidate_news_cache()
            event.status = TelegramNoticiaEvento.STATUS_PROCESSADO
            event.noticia = result.get("noticia")
            event.processado_em = timezone.now()
            event.save(update_fields=["status", "noticia", "processado_em"])
            return event, f"url_{result['outcome']}", {"message": _build_result_message(result), "result": result}

        if looks_like_manual_news_text(raw_text):
            result = sync_news_from_text(raw_text, source_name="Telegram Noticias", publish_drafts=True)
            invalidate_news_cache()
            event.status = TelegramNoticiaEvento.STATUS_PROCESSADO
            event.noticia = result.get("noticia")
            event.processado_em = timezone.now()
            event.save(update_fields=["status", "noticia", "processado_em"])
            return event, f"text_{result['outcome']}", {"message": _build_result_message(result), "result": result}

        event.status = TelegramNoticiaEvento.STATUS_IGNORADO
        event.erro = "Formato nao suportado. Envie 'atualizar 10', um link ou um texto promocional."
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "ignored_unknown_format", {}
    except Exception as exc:
        event.status = TelegramNoticiaEvento.STATUS_ERRO
        event.erro = str(exc)
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "processing_error", {"message": f"Erro ao processar: {exc}"}


def telegram_news_get_updates(limit=20, timeout=0):
    import requests

    response = requests.get(
        build_telegram_news_api_url("getUpdates"),
        params={
            "offset": (TelegramNoticiaEvento.objects.order_by("-update_id").values_list("update_id", flat=True).first() or 0) + 1,
            "limit": max(1, min(int(limit), 100)),
            "timeout": max(0, int(timeout)),
            "allowed_updates": json.dumps(TELEGRAM_NEWS_ALLOWED_UPDATE_TYPES),
        },
        timeout=max(10, int(timeout) + 10),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha no getUpdates do Telegram de noticias: {payload}")
    return payload.get("result") or []


def telegram_news_send_message(chat_id, text):
    import requests

    response = requests.post(
        build_telegram_news_api_url("sendMessage"),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def telegram_news_delete_webhook(drop_pending_updates=False):
    import requests

    response = requests.post(
        build_telegram_news_api_url("deleteWebhook"),
        data={"drop_pending_updates": bool(drop_pending_updates)},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha ao remover webhook do Telegram de noticias: {payload}")
    return payload


def telegram_news_set_webhook(webhook_url):
    import requests

    config = get_telegram_noticias_config()
    data = {
        "url": webhook_url,
        "allowed_updates": json.dumps(TELEGRAM_NEWS_ALLOWED_UPDATE_TYPES),
        "drop_pending_updates": False,
    }
    if config["secret"]:
        data["secret_token"] = config["secret"]
    response = requests.post(
        build_telegram_news_api_url("setWebhook"),
        data=data,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha ao configurar webhook do Telegram de noticias: {payload}")
    return payload
