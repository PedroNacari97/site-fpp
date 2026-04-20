"""Trilha de auditoria do monitoramento (SecurityEvent).

Sempre que o WAF da companhia rejeita o scraper, registramos para deteccao
de padrao (banimento de IP, troca de UA, escalada para proxy, etc.). E o
'sinal' que o agente security pediria — sem isso, falhas silenciosas viram
ponto cego operacional.
"""
from __future__ import annotations

import logging

from accounts.models import SecurityEvent

logger = logging.getLogger(__name__)


def registrar_bloqueio_waf(*, scraper: str, url: str, titulo: str = "") -> None:
    try:
        SecurityEvent.objects.create(
            event_type="scraper_waf_block",
            identifier=scraper[:150],
            details=f"url={url}; title={titulo[:150]}"[:1000],
        )
    except Exception:
        # Auditoria nunca pode quebrar o fluxo principal.
        logger.exception("Falha ao registrar bloqueio WAF para scraper %s", scraper)
