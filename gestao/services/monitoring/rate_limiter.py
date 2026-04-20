"""Token-bucket distribuído por companhia aérea, ancorado no Django cache.

Por que não threading.Semaphore: queremos limitar req/s globalmente entre
qualquer thread/processo do mesmo Django (incluindo gunicorn workers e
managers). O Django cache (locmem em dev, Redis se configurado em prod)
serve esse propósito sem dependência nova.

Por que token-bucket e não fila/leaky: jobs em massa entram em rajada
seguida de longa pausa; o bucket permite usar a folga acumulada quando
a próxima rajada chegar (sem ser DDoS, mas evitando subutilização).
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass

from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuração por companhia. Ajuste fino baseado em IP rep / WAF."""

    rate_per_second: float = 1.5
    burst: int = 5
    max_wait_seconds: float = 30.0


_DEFAULT_CONFIG = RateLimitConfig()

_CONFIG_BY_AIRLINE: dict[str, RateLimitConfig] = {
    # LATAM: deep-link + BFF JSON. Aguenta mais.
    "LATAM": RateLimitConfig(rate_per_second=2.0, burst=8, max_wait_seconds=30.0),
    # GOL: portal completo + Akamai. Conservador.
    "GOL": RateLimitConfig(rate_per_second=1.0, burst=3, max_wait_seconds=45.0),
    # AZUL: ainda em validação, conservador também.
    "AZUL": RateLimitConfig(rate_per_second=1.0, burst=3, max_wait_seconds=45.0),
}


def _config_for(airline_code: str) -> RateLimitConfig:
    return _CONFIG_BY_AIRLINE.get((airline_code or "").upper(), _DEFAULT_CONFIG)


def _bucket_key(airline_code: str) -> str:
    return f"ratelimit:airline:{(airline_code or 'GENERIC').upper()}"


class RateLimitTimeout(Exception):
    """Bucket vazio por mais que ``max_wait_seconds`` — chamada desistiu."""


def _try_acquire(airline_code: str, config: RateLimitConfig) -> float | None:
    """Tenta consumir 1 token. Retorna None se conseguiu, ou segundos a esperar."""
    key = _bucket_key(airline_code)
    now = time.monotonic()
    state = cache.get(key)
    if state is None:
        state = {"tokens": float(config.burst), "ts": now}
    else:
        elapsed = max(0.0, now - state["ts"])
        state["tokens"] = min(
            float(config.burst),
            state["tokens"] + elapsed * config.rate_per_second,
        )
        state["ts"] = now
    if state["tokens"] >= 1.0:
        state["tokens"] -= 1.0
        cache.set(key, state, timeout=600)
        return None
    deficit = 1.0 - state["tokens"]
    espera = deficit / config.rate_per_second
    cache.set(key, state, timeout=600)
    return max(0.05, espera)


@contextmanager
def acquire(airline_code: str, *, config: RateLimitConfig | None = None):
    """Bloqueia até liberar um slot ou estourar o ``max_wait_seconds``.

    Uso:
        with acquire("LATAM"):
            scraper.consultar(...)
    """
    cfg = config or _config_for(airline_code)
    deadline = time.monotonic() + cfg.max_wait_seconds
    while True:
        espera = _try_acquire(airline_code, cfg)
        if espera is None:
            break
        if time.monotonic() + espera > deadline:
            raise RateLimitTimeout(
                f"Rate limit estourado para {airline_code} após {cfg.max_wait_seconds:.0f}s."
            )
        time.sleep(min(espera, 2.0))
    try:
        yield
    finally:
        # Token-bucket não devolve token: o consumo acontece no acquire.
        pass


def reset(airline_code: str) -> None:
    """Útil em testes para zerar o estado do bucket."""
    cache.delete(_bucket_key(airline_code))
