from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from gestao.models import AcompanhamentoPassagem


class ScraperError(Exception):
    """Falha previsível ao consultar o portal da companhia."""


@dataclass
class ResultadoScrape:
    sucesso: bool
    status_reserva: str = AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE
    status_voo: str = AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO
    resumo: str = ""
    duracao_ms: int = 0
    payload_sanitizado: dict = field(default_factory=dict)
    erro: str = ""


class Scraper:
    """Contrato comum dos scrapers das companhias.

    Implementações concretas devem sobrescrever ``consultar`` e definir ``codigo``.
    O scraper recebe localizador + sobrenome (+ opcionalmente a URL de consulta
    cadastrada na ``CompanhiaAerea.site_url``) e devolve um ``ResultadoScrape``
    já com os status normalizados nos choices de ``AcompanhamentoPassagem``.
    """

    codigo: str = ""

    def consultar(
        self,
        localizador: str,
        sobrenome: str,
        *,
        url: str = "",
    ) -> ResultadoScrape:
        raise NotImplementedError


_REGISTRY: dict[str, Callable[[], Scraper]] = {}


def register_scraper(codigo: str, factory: Callable[[], Scraper]) -> None:
    _REGISTRY[codigo] = factory


def get_scraper(codigo: str) -> Scraper | None:
    factory = _REGISTRY.get((codigo or "").upper())
    return factory() if factory else None


# Hardening: localizador PNR e sobrenome sao injetados em uma pagina externa
# via Playwright. Mesmo que o operador seja interno, vale rejeitar qualquer
# coisa fora do alfabeto esperado (defense in depth contra XSS via scraper,
# JS injection no portal da cia, ou poisoning da pagina capturada).
# Aceita PNR (6 chars) e tambem numero de compra/e-ticket (ate 16 chars).
_LOCALIZADOR_RE = re.compile(r"^[A-Z0-9]{5,16}$")
_SOBRENOME_RE = re.compile(r"^[A-Za-zÀ-ÿ' \-]{2,80}$")


def validar_localizador(valor: str) -> str:
    valor = (valor or "").strip().upper()
    if not _LOCALIZADOR_RE.match(valor):
        raise ScraperError(
            "Localizador invalido (5-16 caracteres alfanumericos)."
        )
    return valor


def validar_sobrenome(valor: str) -> str:
    valor = (valor or "").strip()
    if not _SOBRENOME_RE.match(valor):
        raise ScraperError("Sobrenome invalido (apenas letras, espacos, hifen).")
    return valor


_REDACT_PATTERNS = (
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),  # CPF
    re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),  # CNPJ
    re.compile(r"\b[A-Z]{2}\d{6,9}\b"),  # passaporte
    re.compile(r"\b\d{13,19}\b"),  # cartões / bilhetes longos
)


def sanitize_payload(payload):
    """Remove dados pessoais sensíveis antes de gravar no banco/log."""
    if isinstance(payload, dict):
        return {key: sanitize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        cleaned = payload
        for pattern in _REDACT_PATTERNS:
            cleaned = pattern.sub("[REDACTED]", cleaned)
        return cleaned
    return payload
