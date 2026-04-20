"""Bot publico de consulta de status de voo via Telegram.

Fluxo da conversa (state machine em cache, TTL 10 min):

    /start         -> envia menu inline com as companhias suportadas
    callback CIA   -> grava etapa=AGUARDANDO_LOCALIZADOR + cia
                      e pede o numero/codigo conforme cia
    texto          -> grava localizador, pede sobrenome
    texto          -> roda scraper, devolve resumo ao passageiro

Defesas:
- Rate-limit por chat_id (1 consulta a cada 30s) p/ nao estourar WAF da cia.
- Validacao do localizador/sobrenome no proprio scraper (ScraperError).
- Sanitizacao do texto exibido (remove caracteres invisiveis).
- Sem persistencia de PNR/sobrenome em banco — somente cache temporario.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

from gestao.models import CompanhiaAerea
from gestao.services.scrapers import get_scraper
from gestao.services.scrapers.base import ScraperError

logger = logging.getLogger(__name__)


# Etapas da conversa
ETAPA_INICIO = "inicio"
ETAPA_AGUARDANDO_LOCALIZADOR = "aguardando_localizador"
ETAPA_AGUARDANDO_SOBRENOME = "aguardando_sobrenome"

CONV_TTL_SEGUNDOS = 600  # 10 min
RATE_LIMIT_SEGUNDOS = 30
OFFSET_CACHE_KEY = "telegram_status_voo:offset"

# Companhias habilitadas para consulta. Por enquanto so LATAM tem scraper
# pronto; Gol/Azul entram quando o scraper estiver validado.
COMPANHIAS_HABILITADAS = (
    {
        "codigo": CompanhiaAerea.CODIGO_LATAM,
        "rotulo": "LATAM",
        "label_localizador": "Nº da Ordem (ex.: LA1234567IWSR)",
    },
)

ALLOWED_UPDATE_TYPES = ["message", "callback_query"]

_INVISIBLE_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")


# ---------------------------------------------------------------------------
# Configuracao + HTTP
# ---------------------------------------------------------------------------
def _token() -> str:
    token = (getattr(settings, "TELEGRAM_STATUS_VOO_BOT_TOKEN", "") or "").strip()
    if not token:
        raise ValueError(
            "TELEGRAM_STATUS_VOO_BOT_TOKEN nao configurado. Defina a env var."
        )
    return token


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_token()}/{method}"


def get_updates(limit: int = 20, timeout: int = 0) -> list[dict]:
    import requests

    offset = (cache.get(OFFSET_CACHE_KEY) or 0)
    response = requests.get(
        _api_url("getUpdates"),
        params={
            "offset": offset,
            "limit": max(1, min(int(limit), 100)),
            "timeout": max(0, int(timeout)),
            "allowed_updates": json.dumps(ALLOWED_UPDATE_TYPES),
        },
        timeout=max(10, int(timeout) + 10),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(f"Falha no getUpdates: {payload}")
    return payload.get("result") or []


def _avancar_offset(updates: list[dict]) -> None:
    if not updates:
        return
    maior = max(int(u.get("update_id") or 0) for u in updates)
    if maior:
        cache.set(OFFSET_CACHE_KEY, maior + 1, timeout=None)


def send_message(chat_id: int | str, text: str, *, reply_markup: dict | None = None) -> dict:
    import requests

    body: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        body["reply_markup"] = reply_markup
    response = requests.post(_api_url("sendMessage"), json=body, timeout=15)
    response.raise_for_status()
    return response.json()


def answer_callback_query(callback_id: str, text: str = "") -> None:
    import requests

    body: dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        body["text"] = text[:200]
    try:
        requests.post(_api_url("answerCallbackQuery"), json=body, timeout=10)
    except Exception:
        logger.warning("Falha ao responder callback %s", callback_id, exc_info=True)


def delete_webhook() -> dict:
    import requests

    response = requests.post(
        _api_url("deleteWebhook"),
        data={"drop_pending_updates": False},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Estado da conversa
# ---------------------------------------------------------------------------
@dataclass
class EstadoConversa:
    etapa: str = ETAPA_INICIO
    cia_codigo: str = ""
    localizador: str = ""

    def to_dict(self) -> dict:
        return {
            "etapa": self.etapa,
            "cia_codigo": self.cia_codigo,
            "localizador": self.localizador,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "EstadoConversa":
        data = data or {}
        return cls(
            etapa=str(data.get("etapa") or ETAPA_INICIO),
            cia_codigo=str(data.get("cia_codigo") or ""),
            localizador=str(data.get("localizador") or ""),
        )


def _conv_key(chat_id: int | str) -> str:
    return f"telegram_status_voo:conv:{chat_id}"


def carregar_estado(chat_id: int | str) -> EstadoConversa:
    return EstadoConversa.from_dict(cache.get(_conv_key(chat_id)))


def salvar_estado(chat_id: int | str, estado: EstadoConversa) -> None:
    cache.set(_conv_key(chat_id), estado.to_dict(), timeout=CONV_TTL_SEGUNDOS)


def limpar_estado(chat_id: int | str) -> None:
    cache.delete(_conv_key(chat_id))


# ---------------------------------------------------------------------------
# Rate limit por chat_id
# ---------------------------------------------------------------------------
def _rate_key(chat_id: int | str) -> str:
    return f"telegram_status_voo:rl:{chat_id}"


def aguarda_rate_limit(chat_id: int | str) -> int:
    """Retorna 0 se pode consultar; se nao, segundos restantes."""
    ate = cache.get(_rate_key(chat_id))
    if not ate:
        return 0
    restante = int(ate - time.time())
    return max(0, restante)


def marcar_consulta(chat_id: int | str) -> None:
    cache.set(
        _rate_key(chat_id),
        time.time() + RATE_LIMIT_SEGUNDOS,
        timeout=RATE_LIMIT_SEGUNDOS,
    )


# ---------------------------------------------------------------------------
# Helpers de mensagens
# ---------------------------------------------------------------------------
def _sanitize(text: str) -> str:
    cleaned = text or ""
    for char in _INVISIBLE_CHARS:
        cleaned = cleaned.replace(char, "")
    return cleaned.strip()


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _menu_companhias() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": cia["rotulo"],
                    "callback_data": f"cia:{cia['codigo']}",
                }
            ]
            for cia in COMPANHIAS_HABILITADAS
        ]
    }


def _cia_config(codigo: str) -> dict | None:
    for cia in COMPANHIAS_HABILITADAS:
        if cia["codigo"] == codigo:
            return cia
    return None


def _site_url_da_cia(codigo: str) -> str:
    cache_key = f"telegram_status_voo:site_url:{codigo}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    cia = (
        CompanhiaAerea.objects.filter(codigo=codigo)
        .exclude(site_url__isnull=True)
        .exclude(site_url="")
        .first()
    )
    url = getattr(cia, "site_url", "") or ""
    cache.set(cache_key, url, timeout=300)
    return url


# ---------------------------------------------------------------------------
# Formatadores de resposta
# ---------------------------------------------------------------------------
_DATA_HORA_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def _formatar_data_hora(valor: str) -> str:
    if not valor:
        return ""
    m = _DATA_HORA_RE.match(valor)
    if not m:
        return valor[:16]
    ano, mes, dia, hh, mm = m.groups()
    return f"{dia}/{mes}/{ano} {hh}:{mm}"


_STATUS_OPERACIONAL_PT = {
    "NOT_OPERATIONAL": "Programado",
    "ON_TIME": "No horário",
    "SCHEDULED": "Programado",
    "CHECK_IN_OPEN": "Check-in aberto",
    "CHECKIN_OPEN": "Check-in aberto",
    "BOARDING": "Embarque aberto",
    "DELAYED": "Atrasado",
    "CANCELLED": "Cancelado",
    "CANCELED": "Cancelado",
    "DEPARTED": "Em voo",
    "IN_FLIGHT": "Em voo",
    "LANDED": "Pousou",
    "ARRIVED": "Concluído",
}


def _status_humano(status: str) -> str:
    return _STATUS_OPERACIONAL_PT.get((status or "").upper(), status or "—")


def formatar_resposta_latam(payload: dict) -> str:
    """Formata o payload do scraper LATAM em mensagem amigavel."""
    if not payload.get("encontrada"):
        return "❌ " + _escape_html(
            payload.get("erro") or "Reserva não localizada na LATAM."
        )

    reloc = (payload.get("docsStatus") or {}).get("reloc") or ""
    order_id = (payload.get("checkinStatus") or {}).get("orderId") or ""

    linhas: list[str] = ["✈️ <b>Reserva localizada na LATAM</b>", ""]
    if reloc:
        linhas.append(f"<b>Código da Reserva:</b> {_escape_html(reloc)}")
    if order_id:
        linhas.append(f"<b>Nº da Ordem:</b> {_escape_html(order_id)}")
    linhas.append("")

    segmentos = (payload.get("checkinStatus") or {}).get("segments") or []
    if segmentos:
        linhas.append("<b>Trechos</b>")
        for seg in segmentos:
            if not isinstance(seg, dict):
                continue
            voo = seg.get("flightNumber") or ""
            origem = (seg.get("origin") or {}).get("airportCode") or ""
            destino = (seg.get("destination") or {}).get("airportCode") or ""
            partida = _formatar_data_hora(seg.get("departureDate") or "")
            chegada = _formatar_data_hora(seg.get("arrivalDate") or "")
            status_op = _status_humano(
                seg.get("operationalStatus") or seg.get("status") or ""
            )
            linhas.append(
                f"• <b>LA{_escape_html(str(voo))}</b> "
                f"{_escape_html(origem)} → {_escape_html(destino)}"
            )
            if partida:
                linhas.append(f"   Partida: {_escape_html(partida)}")
            if chegada:
                linhas.append(f"   Chegada: {_escape_html(chegada)}")
            linhas.append(f"   Status: {_escape_html(status_op)}")
            linhas.append("")

    passageiros = (payload.get("checkinStatus") or {}).get("passengers") or []
    if passageiros:
        linhas.append("<b>Passageiros</b>")
        for p in passageiros:
            if not isinstance(p, dict):
                continue
            nome = (p.get("firstname") or "").strip()
            sobrenome = (p.get("lastname") or "").strip()
            nome_completo = " ".join(part for part in (nome, sobrenome) if part)
            if nome_completo:
                linhas.append(f"• {_escape_html(nome_completo)}")
        linhas.append("")

    linhas.append(
        "ℹ️ Status fornecido pelo portal da companhia. Para mudanças oficiais, "
        "consulte sempre o aplicativo da LATAM."
    )
    return "\n".join(linhas).strip()


# ---------------------------------------------------------------------------
# Roteador principal
# ---------------------------------------------------------------------------
def _texto_do_update(update: dict) -> tuple[int | None, str]:
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    return chat.get("id"), _sanitize(msg.get("text") or "")


def _callback_do_update(update: dict) -> tuple[int | None, str | None, str]:
    cb = update.get("callback_query")
    if not cb:
        return None, None, ""
    chat = (cb.get("message") or {}).get("chat") or {}
    return chat.get("id"), cb.get("id"), _sanitize(cb.get("data") or "")


def processar_update(update: dict) -> dict:
    """Roteia 1 update do Telegram. Retorna metadados (uteis em log/teste)."""
    # 1) Callback (botao inline) — escolha de cia
    chat_id_cb, cb_id, cb_data = _callback_do_update(update)
    if chat_id_cb and cb_data.startswith("cia:"):
        codigo = cb_data.split(":", 1)[1]
        cia = _cia_config(codigo)
        if cb_id:
            answer_callback_query(cb_id, "OK" if cia else "Companhia indisponivel")
        if not cia:
            send_message(
                chat_id_cb,
                "Essa companhia ainda não está disponível. Tente outra.",
                reply_markup=_menu_companhias(),
            )
            return {"acao": "cia_indisponivel"}
        estado = EstadoConversa(
            etapa=ETAPA_AGUARDANDO_LOCALIZADOR,
            cia_codigo=codigo,
        )
        salvar_estado(chat_id_cb, estado)
        send_message(
            chat_id_cb,
            f"<b>{_escape_html(cia['rotulo'])}</b>\n\n"
            f"Envie o {_escape_html(cia['label_localizador'])}.",
        )
        return {"acao": "pediu_localizador", "cia": codigo}

    # 2) Mensagens de texto
    chat_id, texto = _texto_do_update(update)
    if not chat_id:
        return {"acao": "ignorado"}

    if texto.startswith("/start") or texto.startswith("/help") or texto == "/menu":
        limpar_estado(chat_id)
        send_message(
            chat_id,
            "👋 <b>Status de voo</b>\n\n"
            "Eu consulto o status do seu voo direto no portal da companhia.\n\n"
            "Escolha a companhia para começar:",
            reply_markup=_menu_companhias(),
        )
        return {"acao": "menu"}

    if texto.startswith("/cancelar") or texto.startswith("/sair"):
        limpar_estado(chat_id)
        send_message(chat_id, "Tudo bem. Mande /start quando quiser começar de novo.")
        return {"acao": "cancelou"}

    estado = carregar_estado(chat_id)

    if estado.etapa == ETAPA_AGUARDANDO_LOCALIZADOR:
        estado.localizador = texto.upper()
        estado.etapa = ETAPA_AGUARDANDO_SOBRENOME
        salvar_estado(chat_id, estado)
        send_message(
            chat_id,
            "Agora envie o <b>sobrenome</b> de um dos passageiros (mesmo cadastrado na compra).",
        )
        return {"acao": "pediu_sobrenome"}

    if estado.etapa == ETAPA_AGUARDANDO_SOBRENOME:
        # Rate-limit por chat_id (defense-in-depth contra WAF da cia)
        restante = aguarda_rate_limit(chat_id)
        if restante:
            send_message(
                chat_id,
                f"⏳ Espere {restante}s antes de pedir outra consulta.",
            )
            return {"acao": "rate_limited"}

        sobrenome = texto
        cia = _cia_config(estado.cia_codigo)
        scraper = get_scraper(estado.cia_codigo)
        if not cia or not scraper:
            limpar_estado(chat_id)
            send_message(chat_id, "Companhia indisponível agora. Mande /start.")
            return {"acao": "sem_scraper"}

        marcar_consulta(chat_id)
        send_message(
            chat_id,
            f"🔎 Consultando no portal da {_escape_html(cia['rotulo'])}…",
        )

        try:
            resultado = scraper.consultar(
                estado.localizador,
                sobrenome,
                url=_site_url_da_cia(estado.cia_codigo),
            )
        except ScraperError as exc:
            send_message(chat_id, f"⚠️ {_escape_html(str(exc))}")
            # Mantemos o estado para o usuario tentar de novo o sobrenome.
            return {"acao": "erro_scraper", "msg": str(exc)}
        except Exception as exc:
            logger.exception("Erro inesperado no scraper %s", estado.cia_codigo)
            send_message(
                chat_id,
                "❌ Erro inesperado ao consultar a companhia. Tente daqui a pouco.",
            )
            return {"acao": "erro_inesperado", "msg": str(exc)}

        # Por enquanto so LATAM — formatamos o payload retornado.
        payload = resultado.payload_sanitizado or {}
        if estado.cia_codigo == CompanhiaAerea.CODIGO_LATAM:
            mensagem = formatar_resposta_latam(payload)
        else:
            mensagem = _escape_html(resultado.resumo or "Consulta concluida.")
        send_message(chat_id, mensagem)
        send_message(
            chat_id,
            "Quer consultar outra reserva? Mande /start.",
        )
        limpar_estado(chat_id)
        return {"acao": "ok", "cia": estado.cia_codigo}

    # Sem estado valido — orienta /start
    send_message(
        chat_id,
        "Não entendi. Mande /start para escolher a companhia.",
    )
    return {"acao": "fora_de_contexto"}


def processar_lote(updates: list[dict]) -> dict:
    """Processa um lote de updates e avanca o offset."""
    contadores: dict[str, int] = {}
    for update in updates:
        try:
            meta = processar_update(update)
        except Exception:
            logger.exception("Falha ao processar update %s", update.get("update_id"))
            meta = {"acao": "erro_processamento"}
        chave = meta.get("acao") or "ignorado"
        contadores[chave] = contadores.get(chave, 0) + 1
    _avancar_offset(updates)
    return contadores
