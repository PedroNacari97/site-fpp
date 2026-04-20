from __future__ import annotations

import logging
import time
from typing import Any

from gestao.models import AcompanhamentoPassagem, CompanhiaAerea

from .base import (
    ResultadoScrape,
    Scraper,
    ScraperError,
    register_scraper,
    sanitize_payload,
    validar_localizador,
    validar_sobrenome,
)

logger = logging.getLogger(__name__)


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Chave B2C web extraida do /minhas-viagens.model.json. O APIM Azure do
# b2c-api.voeazul.com.br exige header Ocp-Apim-Subscription-Key + Client=B2C +
# JWT guest em Authorization para liberar o endpoint /reservation/v1/bookings.
_SUBSCRIPTION_KEY = "fb38e642c899485e893eb8d0a373cc17"
_HOST_API = "https://b2c-api.voeazul.com.br"
_HOST_PORTAL = "https://www.voeazul.com.br"


# Status do booking Azul (info.status) observados no payload real.
_MAPA_INFO_STATUS = {
    "CONFIRMED": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "HOLD": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "PENDING": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "CANCELLED": AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
    "CANCELED": AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
    "FLOWN": AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO,
    "COMPLETED": AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO,
}

# Status operacional no nivel de segmento (quando preenchido).
_MAPA_SEGMENT_STATUS_VOO = {
    "SCHEDULED": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "ONTIME": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "ON_TIME": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "CHECKINOPEN": AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    "CHECKIN_OPEN": AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    "CHECKEDIN": AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    "BOARDING": AcompanhamentoPassagem.STATUS_VOO_EMBARQUE,
    "BOARDED": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "DEPARTED": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "INFLIGHT": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "IN_FLIGHT": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "DELAYED": AcompanhamentoPassagem.STATUS_VOO_ATRASADO,
    "CANCELLED": AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
    "CANCELED": AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
    "ARRIVED": AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO,
    "LANDED": AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO,
    "FLOWN": AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO,
}


class AzulScraper(Scraper):
    """Scraper Azul via curl_cffi — 2 chamadas HTTP, sem navegador.

    Pipeline (~1.5s por consulta):
      1. POST ``/authentication/api/authentication/v1/token`` — devolve JWT
         guest. Sem body, exige ``Ocp-Apim-Subscription-Key`` + ``Client: B2C``.
      2. GET ``/reservation/api/reservation/v1/bookings/{PNR}`` com o JWT e
         a subscription key. Retorna reserva completa: journeys, segments,
         passengers, info.status. Nao ha captcha nem Akamai bloqueando (ao
         contrario da GOL).

    Sobrenome e opcional no endpoint, mas se informado e bater com um dos
    passageiros retornados, a consulta segue; caso contrario, rejeita
    (defense in depth contra enumeracao de PNR).
    """

    codigo = CompanhiaAerea.CODIGO_AZUL
    timeout_segundos: int = 30

    def consultar(
        self,
        localizador: str,
        sobrenome: str,
        *,
        url: str = "",
    ) -> ResultadoScrape:
        localizador = validar_localizador(localizador)
        sobrenome = validar_sobrenome(sobrenome)

        inicio = time.monotonic()
        payload = self._consultar_api(localizador, sobrenome)
        duracao_ms = int((time.monotonic() - inicio) * 1000)

        status_reserva = self._derivar_status_reserva(payload)
        status_voo = self._derivar_status_voo(payload)
        resumo = self._resumo_humano(payload)

        sanitizado = sanitize_payload(payload)
        reloc = payload.get("recordLocator") or ""
        if reloc:
            sanitizado["_reloc"] = str(reloc).strip().upper()

        return ResultadoScrape(
            sucesso=True,
            status_reserva=status_reserva,
            status_voo=status_voo,
            resumo=resumo,
            duracao_ms=duracao_ms,
            payload_sanitizado=sanitizado,
        )

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _consultar_api(self, localizador: str, sobrenome: str) -> dict[str, Any]:
        try:
            from curl_cffi import requests as cffi
        except ImportError as exc:
            raise ScraperError(
                "curl_cffi nao esta instalado. Rode: pip install curl-cffi"
            ) from exc

        session = cffi.Session(impersonate="chrome131")

        # Sem warm-up: `b2c-api.voeazul.com.br` e dominio separado do portal,
        # nao compartilha cookies Akamai. Economiza 1-2s por consulta.
        jwt = self._obter_token(session)

        headers_api = {
            "accept": "application/json",
            "authorization": f"Bearer {jwt}",
            "ocp-apim-subscription-key": _SUBSCRIPTION_KEY,
            "client": "B2C",
            "content-type": "application/json",
            "origin": _HOST_PORTAL,
            "referer": f"{_HOST_PORTAL}/",
            "user-agent": _USER_AGENT,
        }

        booking_url = (
            f"{_HOST_API}/reservation/api/reservation/v1/bookings/{localizador}"
        )
        try:
            resp = session.get(
                booking_url, headers=headers_api, timeout=self.timeout_segundos
            )
        except Exception as exc:
            raise ScraperError(
                "Falha tecnica ao consultar Azul (bookings)."
            ) from exc

        if resp.status_code == 404:
            return {
                "fonte": "curl_cffi",
                "encontrada": False,
                "url_consulta": booking_url,
                "erro": "Reserva nao encontrada na Azul.",
            }
        if resp.status_code in (401, 403):
            raise ScraperError(
                f"Portal da Azul bloqueou o acesso (HTTP {resp.status_code})."
            )
        if resp.status_code >= 400:
            raise ScraperError(
                f"API da Azul retornou HTTP {resp.status_code}."
            )

        try:
            envelope = resp.json()
        except Exception as exc:
            raise ScraperError("API da Azul respondeu JSON invalido.") from exc

        data = envelope.get("data") or {}
        if not data or not data.get("recordLocator"):
            return {
                "fonte": "curl_cffi",
                "encontrada": False,
                "url_consulta": booking_url,
                "erro": "Reserva nao encontrada na Azul.",
            }

        if not self._sobrenome_confere(data, sobrenome):
            # Nao revela lista de passageiros — mensagem generica.
            return {
                "fonte": "curl_cffi",
                "encontrada": False,
                "url_consulta": booking_url,
                "erro": "PNR ou sobrenome nao conferem. Verifique os dados.",
            }

        data["fonte"] = "curl_cffi"
        data["encontrada"] = True
        data["url_consulta"] = booking_url
        return data

    def _obter_token(self, session) -> str:
        token_url = (
            f"{_HOST_API}/authentication/api/authentication/v1/token"
        )
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "ocp-apim-subscription-key": _SUBSCRIPTION_KEY,
            "client": "B2C",
            "origin": _HOST_PORTAL,
            "referer": f"{_HOST_PORTAL}/",
            "user-agent": _USER_AGENT,
        }
        try:
            resp = session.post(
                token_url, headers=headers, data="", timeout=self.timeout_segundos
            )
        except Exception as exc:
            raise ScraperError(
                "Falha tecnica ao autenticar na Azul."
            ) from exc

        if resp.status_code != 200:
            raise ScraperError(
                f"Autenticacao Azul retornou HTTP {resp.status_code}."
            )

        try:
            payload = resp.json()
        except Exception as exc:
            raise ScraperError(
                "Resposta do token Azul nao e JSON valido."
            ) from exc

        # Formato observado: {"data": "<jwt>", "notifications": []}
        jwt = payload.get("data")
        if isinstance(jwt, dict):
            jwt = jwt.get("token")
        if not jwt or not isinstance(jwt, str):
            raise ScraperError("Token Azul ausente na resposta.")
        return jwt

    # ------------------------------------------------------------------
    # Normalizacao
    # ------------------------------------------------------------------
    def _sobrenome_confere(self, data: dict, sobrenome: str) -> bool:
        alvo = (sobrenome or "").strip().upper()
        if not alvo:
            return True
        passageiros = data.get("passengers") or []
        for p in passageiros:
            if not isinstance(p, dict):
                continue
            nome = p.get("name") or {}
            last = (nome.get("lastName") or "").strip().upper()
            if last and alvo in last.split():
                return True
            if last and last == alvo:
                return True
        return False

    def _derivar_status_reserva(self, payload: dict) -> str:
        if not payload.get("encontrada"):
            return AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE

        segmentos = self._segmentos(payload)
        status_segs = [self._status_segmento(s) for s in segmentos]
        status_segs = [s for s in status_segs if s]

        if status_segs and any(s in ("CANCELLED", "CANCELED") for s in status_segs):
            return AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO
        if status_segs and all(
            s in ("ARRIVED", "LANDED", "FLOWN") for s in status_segs
        ):
            return AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO
        if any(
            s in ("BOARDED", "DEPARTED", "IN_FLIGHT", "INFLIGHT", "BOARDING")
            for s in status_segs
        ):
            return AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO

        info_status = str((payload.get("info") or {}).get("status") or "").upper()
        if info_status:
            mapeado = _MAPA_INFO_STATUS.get(info_status)
            if mapeado:
                return mapeado

        if segmentos:
            return AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO
        return AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE

    def _derivar_status_voo(self, payload: dict) -> str:
        if not payload.get("encontrada"):
            return AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO
        segmentos = self._segmentos(payload)
        if not segmentos:
            return AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO

        # Pega o proximo segmento que ainda nao terminou.
        alvo = next(
            (
                s
                for s in segmentos
                if self._status_segmento(s)
                not in ("ARRIVED", "LANDED", "FLOWN", "DEPARTED", "IN_FLIGHT")
            ),
            segmentos[0],
        )
        status = self._status_segmento(alvo)
        if status:
            mapeado = _MAPA_SEGMENT_STATUS_VOO.get(status)
            if mapeado:
                return mapeado

        # Sem status operacional (voo futuro distante): cai no info.status.
        info_status = str((payload.get("info") or {}).get("status") or "").upper()
        if info_status == "CANCELLED":
            return AcompanhamentoPassagem.STATUS_VOO_CANCELADO
        if info_status == "FLOWN":
            return AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO
        return AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO

    def _segmentos(self, payload: dict) -> list[dict]:
        out: list[dict] = []
        for j in payload.get("journeys") or []:
            if not isinstance(j, dict):
                continue
            for seg in j.get("segments") or []:
                if isinstance(seg, dict):
                    out.append(seg)
        return out

    def _status_segmento(self, segmento: dict) -> str:
        raw = str(
            segmento.get("status")
            or segmento.get("operationalStatus")
            or ""
        ).upper().replace(" ", "").replace("-", "")
        return raw

    def _resumo_humano(self, payload: dict) -> str:
        if not payload.get("encontrada"):
            return payload.get("erro") or "Reserva nao localizada na Azul."

        partes: list[str] = []
        reloc = payload.get("recordLocator") or ""
        if reloc:
            partes.append(f"Codigo reserva {reloc}")
        info_status = (payload.get("info") or {}).get("status") or ""
        if info_status:
            partes.append(f"Status: {info_status}")

        for seg in self._segmentos(payload)[:6]:
            ident = seg.get("identifier") or {}
            voo = ident.get("identifierKey") or ""
            carrier = ident.get("carrierCode") or "AD"
            origem = ident.get("departureCode") or ""
            destino = ident.get("arrivalCode") or ""
            std = (ident.get("std") or "")[:10]
            status = self._status_segmento(seg) or "?"
            partes.append(
                f"{carrier}{voo} {origem}->{destino} {std} [{status}]".strip()
            )

        passageiros = payload.get("passengers") or []
        if passageiros:
            nomes = []
            for p in passageiros[:3]:
                nome = p.get("name") or {}
                nome_str = (
                    f"{(nome.get('firstName') or '').strip()} "
                    f"{(nome.get('lastName') or '').strip()}"
                ).strip()
                if nome_str:
                    nomes.append(nome_str)
            if nomes:
                partes.append(f"Passageiros: {', '.join(nomes)}")

        return " | ".join(p for p in partes if p)[:800]


register_scraper(CompanhiaAerea.CODIGO_AZUL, AzulScraper)
