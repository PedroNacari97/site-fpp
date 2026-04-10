import hashlib
import json
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from gestao.models import AlertaViagem, TelegramAlertaEvento
from gestao.services.alerta_parser import parse_alerta_bruto
from gestao.services.interesses_viagem import sync_alerta_interest_matches
from gestao.services.alerta_upsert import create_or_update_alerta


TELEGRAM_ALLOWED_UPDATE_TYPES = ["message", "channel_post"]


def get_telegram_alertas_config():
    allowed_chat_ids = set()
    for item in getattr(settings, "TELEGRAM_ALERTS_ALLOWED_CHAT_IDS", []):
        cleaned = str(item).strip()
        if cleaned:
            allowed_chat_ids.add(cleaned)
    return {
        "token": getattr(settings, "TELEGRAM_ALERTS_BOT_TOKEN", "").strip(),
        "secret": getattr(settings, "TELEGRAM_ALERTS_WEBHOOK_SECRET", "").strip(),
        "allowed_chat_ids": allowed_chat_ids,
    }


def build_telegram_api_url(method_name):
    config = get_telegram_alertas_config()
    token = config["token"]
    if not token:
        raise ValueError("TELEGRAM_ALERTS_BOT_TOKEN não configurado.")
    return f"https://api.telegram.org/bot{token}/{method_name}"


def _extract_message(update):
    message = update.get("channel_post") or update.get("message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = (message.get("text") or message.get("caption") or "").strip()
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


def _required_parsed_fields(parsed):
    required_fields = [
        "titulo",
        "continente",
        "pais",
        "cidade_destino",
        "origem",
        "destino",
        "classe",
        "programa_fidelidade",
        "companhia_aerea",
        "valor_milhas",
    ]
    return [field for field in required_fields if not parsed.get(field)]


def _find_recent_duplicate(message_hash, chat_id):
    return None


@transaction.atomic
def process_telegram_alert_update(update):
    update_id = update.get("update_id")
    if update_id is None:
        raise ValueError("Update do Telegram sem update_id.")

    message = _extract_message(update)
    raw_text = message["text"]
    message_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else ""

    event, created = TelegramAlertaEvento.objects.get_or_create(
        update_id=update_id,
        defaults={
            "chat_id": message["chat_id"],
            "message_id": message["message_id"],
            "chat_nome": message["chat_nome"],
            "remetente": message["remetente"],
            "mensagem_hash": message_hash,
            "texto_bruto": raw_text,
            "payload_json": update,
            "status": TelegramAlertaEvento.STATUS_RECEBIDO,
        },
    )
    if not created:
        return event, "duplicate_update"

    config = get_telegram_alertas_config()
    chat_id = message["chat_id"]
    if config["allowed_chat_ids"] and str(chat_id) not in config["allowed_chat_ids"]:
        event.status = TelegramAlertaEvento.STATUS_IGNORADO
        event.erro = "Chat não autorizado para cadastro automático de alertas."
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "ignored_chat"

    if not raw_text:
        event.status = TelegramAlertaEvento.STATUS_IGNORADO
        event.erro = "Mensagem sem texto útil para interpretar alerta."
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "ignored_empty"

    duplicate_event = _find_recent_duplicate(message_hash, chat_id)
    if duplicate_event and duplicate_event.id != event.id:
        event.status = TelegramAlertaEvento.STATUS_IGNORADO
        event.erro = "Mensagem duplicada já processada anteriormente."
        event.alerta = duplicate_event.alerta
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "alerta", "processado_em"])
        return event, "ignored_duplicate_message"

    parsed = parse_alerta_bruto(raw_text)
    missing_fields = _required_parsed_fields(parsed)
    if missing_fields:
        event.status = TelegramAlertaEvento.STATUS_ERRO
        event.erro = "Campos obrigatórios não identificados: " + ", ".join(missing_fields)
        event.processado_em = timezone.now()
        event.save(update_fields=["status", "erro", "processado_em"])
        return event, "parse_error"

    alerta, created = create_or_update_alerta(parsed)
    sync_alerta_interest_matches(alerta)
    event.status = TelegramAlertaEvento.STATUS_PROCESSADO
    event.alerta = alerta
    event.processado_em = timezone.now()
    event.save(update_fields=["status", "alerta", "processado_em"])
    return event, "created" if created else "updated"


def telegram_get_updates(limit=20, timeout=0):
    import requests

    response = requests.get(
        build_telegram_api_url("getUpdates"),
        params={
            "offset": (TelegramAlertaEvento.objects.order_by("-update_id").values_list("update_id", flat=True).first() or 0) + 1,
            "limit": max(1, min(int(limit), 100)),
            "timeout": max(0, int(timeout)),
            "allowed_updates": json.dumps(TELEGRAM_ALLOWED_UPDATE_TYPES),
        },
        timeout=max(10, int(timeout) + 10),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha no getUpdates do Telegram: {payload}")
    return payload.get("result") or []


def telegram_send_message(chat_id, text):
    import requests

    response = requests.post(
        build_telegram_api_url("sendMessage"),
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def telegram_set_webhook(webhook_url):
    import requests

    config = get_telegram_alertas_config()
    data = {
        "url": webhook_url,
        "allowed_updates": json.dumps(TELEGRAM_ALLOWED_UPDATE_TYPES),
        "drop_pending_updates": False,
    }
    if config["secret"]:
        data["secret_token"] = config["secret"]
    response = requests.post(
        build_telegram_api_url("setWebhook"),
        data=data,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha ao configurar webhook do Telegram: {payload}")
    return payload


def telegram_delete_webhook(drop_pending_updates=False):
    import requests

    response = requests.post(
        build_telegram_api_url("deleteWebhook"),
        data={"drop_pending_updates": bool(drop_pending_updates)},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha ao remover webhook do Telegram: {payload}")
    return payload
