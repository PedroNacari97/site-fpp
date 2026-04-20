from __future__ import annotations

import logging
import time
import uuid
from typing import Any
from urllib.parse import quote

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


WAF_MARKERS = (
    "access denied",
    "acceso denegado",
    "acesso negado",
    "for security reasons",
    "por motivos de seguridad",
    "request blocked",
)


# Mapa operationalStatus da BFF LATAM -> STATUS_VOO canonico.
# Valores observados: NOT_OPERATIONAL (voo futuro), ON_TIME, DELAYED, CANCELLED,
# BOARDING, DEPARTED, LANDED, CHECK_IN_OPEN.
_MAPA_STATUS_VOO = {
    "NOT_OPERATIONAL": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "ON_TIME": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "SCHEDULED": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
    "CHECK_IN_OPEN": AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    "CHECKIN_OPEN": AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    "BOARDING": AcompanhamentoPassagem.STATUS_VOO_EMBARQUE,
    "DELAYED": AcompanhamentoPassagem.STATUS_VOO_ATRASADO,
    "CANCELLED": AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
    "CANCELED": AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
    "DEPARTED": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "IN_FLIGHT": AcompanhamentoPassagem.STATUS_VOO_EMBARCADO,
    "LANDED": AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO,
    "ARRIVED": AcompanhamentoPassagem.STATUS_VOO_CONCLUIDO,
}

# Mapa operationalStatus -> STATUS_RESERVA. Espelha a resposta literal da
# LATAM: voo futuro vira "programado" (não "emitido"), check-in/embarque
# refletem o portal, e estados terminais (LANDED/DEPARTED) sobem para
# embarcado/concluido. Decisão do produto: preferimos a nomenclatura
# operacional que o passageiro vê na própria LATAM.
_MAPA_STATUS_RESERVA = {
    "NOT_OPERATIONAL": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "ON_TIME": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "SCHEDULED": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "CHECK_IN_OPEN": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "CHECKIN_OPEN": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "BOARDING": AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO,
    "DELAYED": AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO,
    "CANCELLED": AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
    "CANCELED": AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
    "DEPARTED": AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO,
    "IN_FLIGHT": AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO,
    "LANDED": AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO,
    "ARRIVED": AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO,
}


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _detectar_waf(texto: str, titulo: str) -> bool:
    alvo = f"{titulo} {texto}".lower()
    return any(marker in alvo for marker in WAF_MARKERS)


class LatamScraper(Scraper):
    """Scraper LATAM via curl_cffi — 2 chamadas HTTP puras, sem navegador.

    Pipeline (~2s por consulta):
      1. GET ``/br/pt/minhas-viagens/second-detail?orderId=X&lastname=Y``
         para capturar cookies Akamai (``_abck``, ``bm_sz``, ``_xp_session``)
         na session do curl_cffi com impersonate chrome131.
      2. POST ``/bff/web/passenger-checkin/orders/{orderId}/checkin_status``
         reusando a mesma session, com headers proprietarios ``x-latam-*``
         e body ``{"lastName": Y}``. Resposta JSON tem status operacional,
         segmentos, passageiros e o codigo da reserva (reloc / PNR 6 chars).

    Zero Playwright em produçao — mantido apenas como fallback opcional se o
    BFF estiver indisponivel. Economia de ~$15/mes Railway (nenhum container
    Chromium separado).
    """

    codigo = CompanhiaAerea.CODIGO_LATAM

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
        url_alvo = (url or "").strip()
        if not url_alvo:
            raise ScraperError(
                "URL da LATAM nao cadastrada. Configure CompanhiaAerea.site_url."
            )

        inicio = time.monotonic()
        payload = self._consultar_via_bff(localizador, sobrenome, url_alvo)
        duracao_ms = int((time.monotonic() - inicio) * 1000)

        status_reserva = self._derivar_status_reserva(payload)
        status_voo = self._derivar_status_voo(payload)
        resumo = self._resumo_humano(payload)

        # Promove o reloc (PNR de 6 chars) para chave de topo no payload
        # sanitizado. O orderId fica em ``localizador_consulta``; o reloc é
        # o que a LATAM exibe para o passageiro. ``sanitize_payload`` redige
        # CPF/CNPJ/passaporte/cartões mas preserva o PNR (5-6 chars).
        sanitizado = sanitize_payload(payload)
        reloc = (payload.get("docsStatus") or {}).get("reloc") or ""
        if reloc:
            sanitizado["_reloc"] = str(reloc).strip().upper()
        order_id = (payload.get("checkinStatus") or {}).get("orderId") or ""
        if order_id:
            sanitizado["_order_id"] = str(order_id).strip().upper()

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
    def _consultar_via_bff(
        self,
        localizador: str,
        sobrenome: str,
        url_alvo: str,
    ) -> dict[str, Any]:
        try:
            from curl_cffi import requests as cffi
        except ImportError as exc:
            raise ScraperError(
                "curl_cffi nao esta instalado. Rode: pip install curl-cffi"
            ) from exc

        host = self._derivar_host(url_alvo)
        session = cffi.Session(impersonate="chrome131")

        deep_link = (
            f"{host}/br/pt/minhas-viagens/second-detail"
            f"?orderId={quote(localizador)}&lastname={quote(sobrenome)}"
        )
        headers_html = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "pt-BR,pt;q=0.9",
            "user-agent": _USER_AGENT,
            "upgrade-insecure-requests": "1",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        try:
            resp_html = session.get(
                deep_link, headers=headers_html, timeout=self.timeout_segundos
            )
        except Exception as exc:
            raise ScraperError(
                "Falha tecnica ao consultar LATAM (deep-link)."
            ) from exc

        if resp_html.status_code in (401, 403):
            raise ScraperError(
                "Portal da LATAM bloqueou o acesso (HTTP %s)." % resp_html.status_code
            )
        if _detectar_waf(resp_html.text or "", ""):
            from gestao.services.monitoring.security_log import registrar_bloqueio_waf

            registrar_bloqueio_waf(
                scraper="LATAM", url=deep_link, titulo="WAF on deep-link"
            )
            raise ScraperError("Portal da LATAM bloqueou o acesso (WAF). Tente mais tarde.")

        bff_url = (
            f"{host}/bff/web/passenger-checkin/orders/{quote(localizador)}"
            "/checkin_status"
        )
        headers_bff = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "pt-BR",
            "content-type": "application/json",
            "origin": host,
            "referer": (
                f"{host}/br/pt/check-in/status"
                f"?orderId={quote(localizador)}&lastName={quote(sobrenome)}"
            ),
            "user-agent": _USER_AGENT,
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-latam-action-name": "passenger-checkin.search-order.search-order",
            "x-latam-app-session-id": str(uuid.uuid4()),
            "x-latam-application-country": "br",
            "x-latam-application-lang": "pt",
            "x-latam-application-name": "web-passenger-checkin",
            "x-latam-application-oc": "br",
            "x-latam-client-name": "web-passenger-checkin",
            "x-latam-home-request": "BR",
            "x-latam-request-id": str(uuid.uuid4()),
            "x-latam-track-id": str(uuid.uuid4()),
        }
        try:
            resp_bff = session.post(
                bff_url,
                headers=headers_bff,
                json={"lastName": sobrenome},
                timeout=self.timeout_segundos,
            )
        except Exception as exc:
            raise ScraperError(
                "Falha tecnica ao consultar LATAM (BFF)."
            ) from exc

        if resp_bff.status_code == 404:
            return {
                "fonte": "curl_cffi",
                "encontrada": False,
                "url_consulta": deep_link,
                "erro": "Reserva nao encontrada na LATAM.",
            }
        if resp_bff.status_code == 400:
            # BFF retorna 400 quando os dados nao batem (PNR/sobrenome errado)
            return {
                "fonte": "curl_cffi",
                "encontrada": False,
                "url_consulta": deep_link,
                "erro": "PNR ou sobrenome nao conferem. Verifique os dados.",
            }
        if resp_bff.status_code >= 400:
            raise ScraperError(
                f"BFF da LATAM retornou HTTP {resp_bff.status_code}."
            )

        try:
            data = resp_bff.json()
        except Exception as exc:
            raise ScraperError("BFF da LATAM respondeu JSON invalido.") from exc

        data["fonte"] = "curl_cffi"
        data["encontrada"] = True
        data["url_consulta"] = deep_link
        return data

    def _derivar_host(self, url_alvo: str) -> str:
        import re as _re

        m = _re.match(r"^(https?://[^/]+)", url_alvo)
        return m.group(1) if m else "https://www.latamairlines.com"

    # ------------------------------------------------------------------
    # Normalizacao
    # ------------------------------------------------------------------
    def _derivar_status_reserva(self, payload: dict) -> str:
        """Espelha o ``operationalStatus`` da LATAM, sem regra paralela.

        Decisão de produto: o cliente quer ver "programado" (que é o que a
        LATAM mostra para voo futuro), não "emitido" derivado de
        ``docsStatus``. Quando todos os trechos já voaram, sobe para
        concluído; se algum cancelou, reserva cancelada.
        """
        if not payload.get("encontrada"):
            return AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE

        segmentos = self._segmentos(payload)
        if not segmentos:
            return AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE

        status_voos = [self._status_operacional(s) for s in segmentos]

        if any(s in ("CANCELLED", "CANCELED") for s in status_voos):
            return AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO
        if status_voos and all(s in ("LANDED", "ARRIVED") for s in status_voos):
            return AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO
        if any(s in ("DEPARTED", "IN_FLIGHT", "BOARDING") for s in status_voos):
            return AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO

        # Próximo trecho não finalizado define o estado da reserva.
        proximo = next(
            (s for s in status_voos if s not in ("LANDED", "ARRIVED")),
            status_voos[0],
        )
        return _MAPA_STATUS_RESERVA.get(
            proximo, AcompanhamentoPassagem.STATUS_RESERVA_PROGRAMADO
        )

    def _derivar_status_voo(self, payload: dict) -> str:
        if not payload.get("encontrada"):
            return AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO
        segmentos = self._segmentos(payload)
        if not segmentos:
            return AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO
        # Pega o proximo segmento nao finalizado (ou o primeiro).
        alvo = next(
            (
                s
                for s in segmentos
                if self._status_operacional(s)
                not in ("LANDED", "ARRIVED", "DEPARTED", "IN_FLIGHT")
            ),
            segmentos[0],
        )
        canonical = self._status_operacional(alvo)
        return _MAPA_STATUS_VOO.get(
            canonical, AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO
        )

    def _segmentos(self, payload: dict) -> list[dict]:
        checkin = payload.get("checkinStatus") or {}
        segs = checkin.get("segments") or []
        return [s for s in segs if isinstance(s, dict)]

    def _status_operacional(self, segmento: dict) -> str:
        return str(
            segmento.get("operationalStatus")
            or segmento.get("status")
            or ""
        ).upper()

    def _resumo_humano(self, payload: dict) -> str:
        if not payload.get("encontrada"):
            return payload.get("erro") or "Reserva nao localizada na LATAM."
        partes: list[str] = []
        reloc = (payload.get("docsStatus") or {}).get("reloc") or ""
        order_id = (payload.get("checkinStatus") or {}).get("orderId") or ""
        if reloc:
            partes.append(f"Codigo reserva {reloc}")
        if order_id:
            partes.append(f"Ordem {order_id}")
        for seg in self._segmentos(payload)[:4]:
            flight = seg.get("flightNumber") or ""
            origem = (seg.get("origin") or {}).get("airportCode") or ""
            destino = (seg.get("destination") or {}).get("airportCode") or ""
            data = seg.get("departureDate") or ""
            status = self._status_operacional(seg) or "?"
            partes.append(
                f"LA{flight} {origem}->{destino} {data[:10]} [{status}]".strip()
            )
        passageiros = (payload.get("checkinStatus") or {}).get("passengers") or []
        if passageiros:
            nomes = ", ".join(
                f"{(p.get('firstname') or '').strip()} {(p.get('lastname') or '').strip()}".strip()
                for p in passageiros[:3]
            )
            if nomes:
                partes.append(f"Passageiros: {nomes}")
        return " | ".join(p for p in partes if p)[:800]


register_scraper(CompanhiaAerea.CODIGO_LATAM, LatamScraper)
