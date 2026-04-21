"""Servicos do paywall de artigos (flexible sampling).

- `is_verified_search_bot` — verifica Googlebot/Bingbot via FCrDNS com cache Redis.
- `truncar_corpo_artigo` — retorna apenas os N primeiros paragrafos do HTML.

Motivacao: artigos exigem login. Para evitar cloaking (e indexacao zero), o
servidor entrega corpo completo apenas para bots de busca verificados via DNS
reverso+forward (padrao oficial Google). Usuario anonimo recebe versao truncada
+ paywall card com CTA de cadastro. Esquema Article marca `isAccessibleForFree:
false` + `hasPart` com cssSelector — declaracao oficial de flexible sampling.
"""
from __future__ import annotations

import logging
import re
import socket
from typing import Iterable

from django.core.cache import cache


logger = logging.getLogger(__name__)


# Sufixos de hostname reverso confiaveis por crawler.
# Fonte oficial: https://developers.google.com/search/docs/crawling-indexing/verifying-googlebot
_TRUSTED_HOST_SUFFIXES: dict[str, tuple[str, ...]] = {
    "googlebot": (".googlebot.com", ".google.com"),
    "bingbot": (".search.msn.com",),
}

# Padroes de User-Agent por crawler (lowercase).
_BOT_UA_PATTERNS: dict[str, tuple[str, ...]] = {
    "googlebot": ("googlebot", "adsbot-google", "mediapartners-google"),
    "bingbot": ("bingbot",),
}

BOT_VERIFY_TTL_OK = 60 * 60 * 24  # 24h
BOT_VERIFY_TTL_FAIL = 60 * 5  # 5 min — UA forjado pode tentar de novo rapido


def _identify_claimed_bot(user_agent: str) -> str | None:
    ua = (user_agent or "").lower()
    for bot_name, patterns in _BOT_UA_PATTERNS.items():
        if any(pattern in ua for pattern in patterns):
            return bot_name
    return None


def _is_trusted_hostname(hostname: str, suffixes: Iterable[str]) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return any(host.endswith(suffix) for suffix in suffixes)


def is_verified_search_bot(ip_address: str, user_agent: str) -> bool:
    """Valida Googlebot/Bingbot via FCrDNS com cache.

    FCrDNS = Forward-Confirmed reverse DNS:
      1. reverse lookup do IP retorna hostname legitimo (ex: crawl.googlebot.com)
      2. forward lookup desse hostname retorna o mesmo IP

    Qualquer atacante pode forjar `User-Agent: Googlebot`, mas nao consegue
    controlar o PTR DNS do proprio IP. Por isso validamos antes de entregar
    conteudo completo.
    """
    if not ip_address:
        return False

    bot_name = _identify_claimed_bot(user_agent)
    if not bot_name:
        return False

    cache_key = f"portal:bot_verify:{bot_name}:{ip_address}"
    cached = cache.get(cache_key)
    if cached == "yes":
        return True
    if cached == "no":
        return False

    suffixes = _TRUSTED_HOST_SUFFIXES.get(bot_name, ())
    try:
        hostname, _aliases, _ips = socket.gethostbyaddr(ip_address)
    except (socket.herror, socket.gaierror, OSError) as exc:
        logger.info("paywall.fcrdns reverse_fail ip=%s ua=%s err=%s", ip_address, bot_name, exc)
        cache.set(cache_key, "no", BOT_VERIFY_TTL_FAIL)
        return False

    if not _is_trusted_hostname(hostname, suffixes):
        logger.warning(
            "paywall.fcrdns untrusted_host ip=%s ua=%s hostname=%s",
            ip_address,
            bot_name,
            hostname,
        )
        cache.set(cache_key, "no", BOT_VERIFY_TTL_FAIL)
        return False

    try:
        _name, _aliases, forward_ips = socket.gethostbyname_ex(hostname)
    except (socket.herror, socket.gaierror, OSError) as exc:
        logger.info(
            "paywall.fcrdns forward_fail ip=%s hostname=%s err=%s",
            ip_address,
            hostname,
            exc,
        )
        cache.set(cache_key, "no", BOT_VERIFY_TTL_FAIL)
        return False

    verified = ip_address in forward_ips
    cache.set(cache_key, "yes" if verified else "no", BOT_VERIFY_TTL_OK if verified else BOT_VERIFY_TTL_FAIL)
    if not verified:
        logger.warning(
            "paywall.fcrdns forward_mismatch ip=%s hostname=%s forward_ips=%s",
            ip_address,
            hostname,
            forward_ips,
        )
    return verified


# --- Truncagem do corpo -------------------------------------------------------

# Tags de bloco consideradas "paragrafo" para corte do paywall.
# <p> e intencional; <h2>/<h3> tambem contam se aparecerem antes do 2o paragrafo
# (garante que o corte nao fique orfao sem heading proximo).
_BLOCK_RE = re.compile(
    r"<(?:p|h2|h3|ul|ol|blockquote)\b[^>]*>.*?</(?:p|h2|h3|ul|ol|blockquote)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_PARAGRAFO_RE = re.compile(r"<p\b[^>]*>.*?</p>", flags=re.IGNORECASE | re.DOTALL)


def truncar_corpo_artigo(html: str, paragrafos: int = 2) -> str:
    """Retorna apenas os primeiros `paragrafos` blocos `<p>`.

    Se o HTML nao tem paragrafos detectaveis, devolve prefixo seguro de 600
    chars — nunca o corpo inteiro. Preserva sanitizacao previa do corpo.
    """
    if not html:
        return ""
    matches = _PARAGRAFO_RE.findall(html)
    if matches:
        return "".join(matches[:paragrafos])
    # Fallback: sem <p> detectado, corta cru (sem tags finais aninhadas por sorte).
    return html[:600]


# --- Extracao de sumario (TOC) ------------------------------------------------

# Captura o texto interno de cada <h2> do corpo, ignorando atributos e tags
# internas simples (<strong>, <em> etc). Usado para gerar TOC server-side
# quando o paywall trunca o corpo: o usuario anonimo ve os temas todos do
# artigo (motivacao para cadastrar) sem precisar do JS rodar sobre o HTML
# completo (que nao e enviado).
_H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", flags=re.IGNORECASE | re.DOTALL)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def extrair_titulos_h2(html: str) -> list[str]:
    """Devolve lista com texto puro de cada <h2> do HTML, na ordem original."""
    if not html:
        return []
    titulos: list[str] = []
    for raw in _H2_RE.findall(html):
        texto = _TAG_STRIP_RE.sub("", raw).strip()
        if texto:
            titulos.append(texto)
    return titulos
