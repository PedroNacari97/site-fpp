"""Catalogo de marcas consumido pelo gerador de imagens (ai_pipeline).

Fonte de verdade: tabela ``gestao.MarcaCatalogo``. O CSV
``marcas_api_brandfetch_v2.csv`` na raiz do projeto e apenas o SEED usado
pelo management command ``import_marcas_catalogo`` para popular o banco.

API publica (mantida para compatibilidade com ``portal/services/ai_pipeline.py``):
    - ``load_brand_catalog() -> list[dict]`` (cacheada)
    - cada dict tem as chaves: ``keywords``, ``name``, ``cor_hex``, ``logo_url``

Se a tabela estiver vazia ou inacessivel (ex.: boot do app antes do migrate),
caimos no ``_FALLBACK_BRAND_CATALOG`` hardcoded para nao quebrar o pipeline.
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


# Catalogo minimo usado como fallback quando a tabela ``MarcaCatalogo``
# ainda nao foi populada (bootstrap, testes, ambiente local sem seed).
# Em producao, apos rodar ``manage.py import_marcas_catalogo`` a lista
# completa vem do banco.
_FALLBACK_BRAND_CATALOG: list[dict] = [
    # Programas de Pontos/Milhas
    {"keywords": ["latam pass", "latampass"],         "name": "LATAM Pass",          "cor_hex": "#7000ac", "logo_url": ""},
    {"keywords": ["azul fidelidade", "tudo azul"],    "name": "Azul Fidelidade",      "cor_hex": "#5061aa", "logo_url": ""},
    {"keywords": ["livelo"],                          "name": "Livelo",               "cor_hex": "#df0978", "logo_url": "https://cdn.brandfetch.io/idcBSnzgu0/w/180/h/180/theme/dark/logo.png"},
    {"keywords": ["smiles"],                          "name": "Smiles",               "cor_hex": "#eb7f02", "logo_url": "https://cdn.brandfetch.io/idGtn14sSi/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["esfera"],                          "name": "Esfera",               "cor_hex": "#2e30ad", "logo_url": "https://cdn.brandfetch.io/idw4hqM92g/w/256/h/55/theme/dark/logo.png"},
    {"keywords": ["dotz"],                            "name": "Dotz",                 "cor_hex": "#fd7e14", "logo_url": "https://cdn.brandfetch.io/idxu_hsnK3/w/240/h/125/theme/dark/logo.png"},
    {"keywords": ["premmia"],                         "name": "Premmia",              "cor_hex": "#31db4e", "logo_url": "https://cdn.brandfetch.io/id0LIQIb4i/w/820/h/323/theme/light/logo.png"},
    # Companhias Aereas
    {"keywords": ["latam airlines", "latam"],         "name": "LATAM Airlines",       "cor_hex": "#7000ac", "logo_url": ""},
    {"keywords": ["gol airlines", "voe gol", " gol "], "name": "GOL",                 "cor_hex": "#ff7020", "logo_url": "https://cdn.brandfetch.io/id1XOAor3l/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["azul airlines", "voe azul", " azul "], "name": "Azul Airlines",   "cor_hex": "#5061aa", "logo_url": "https://cdn.brandfetch.io/idY8UKgMnI/w/389/h/389/theme/dark/icon.jpeg"},
    {"keywords": ["avianca"],                         "name": "Avianca",              "cor_hex": "#c8102e", "logo_url": "https://cdn.brandfetch.io/idgYzF_oJj/w/960/h/960/theme/dark/icon.jpeg"},
    {"keywords": ["tap air", "tap portugal", " tap "], "name": "TAP Air Portugal",     "cor_hex": "#eb2d2e", "logo_url": "https://cdn.brandfetch.io/idYGJZtC7P/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["emirates"],                        "name": "Emirates",             "cor_hex": "#c60c30", "logo_url": "https://cdn.brandfetch.io/idItGcrKZZ/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["qatar airways", "qatar"],          "name": "Qatar Airways",        "cor_hex": "#8e2157", "logo_url": "https://cdn.brandfetch.io/idZKewuK9S/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["lufthansa"],                       "name": "Lufthansa",            "cor_hex": "#05164d", "logo_url": ""},
    {"keywords": ["united airlines", "united"],       "name": "United Airlines",      "cor_hex": "#1414d2", "logo_url": ""},
    {"keywords": ["delta airlines", "delta"],         "name": "Delta",                "cor_hex": "#e51937", "logo_url": ""},
    {"keywords": ["american airlines"],               "name": "American Airlines",    "cor_hex": "#0078d2", "logo_url": ""},
    {"keywords": ["british airways"],                 "name": "British Airways",      "cor_hex": "#2f5e9e", "logo_url": ""},
    {"keywords": ["copa airlines", "copa air"],       "name": "Copa Airlines",        "cor_hex": "#0032a0", "logo_url": "https://cdn.brandfetch.io/id7Krz3SDX/w/331/h/331/theme/dark/icon.jpeg"},
    {"keywords": ["turkish airlines", "turkish"],     "name": "Turkish Airlines",     "cor_hex": "#c70a0c", "logo_url": ""},
    {"keywords": ["klm"],                             "name": "KLM",                  "cor_hex": "#0095db", "logo_url": "https://cdn.brandfetch.io/id6HKDgYDF/w/820/h/547/theme/dark/logo.png"},
    {"keywords": ["iberia"],                          "name": "Iberia",               "cor_hex": "#d7192d", "logo_url": "https://cdn.brandfetch.io/id7Ift3wzp/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["swiss"],                           "name": "Swiss",                "cor_hex": "#e60005", "logo_url": ""},
    {"keywords": ["aerolineas"],                      "name": "Aerol\u00edneas Argentinas", "cor_hex": "#f6bb60", "logo_url": "https://cdn.brandfetch.io/idh0TdD3uK/w/200/h/200/theme/dark/icon.png"},
    # Bancos
    {"keywords": ["nubank", "nu pagamentos"],         "name": "Nubank",               "cor_hex": "#8a05be", "logo_url": "https://cdn.brandfetch.io/idXWQ2eElW/w/1079/h/1079/theme/dark/icon.png"},
    {"keywords": ["itau", "ita\u00fa"],                "name": "Ita\u00fa",             "cor_hex": "#FF6200", "logo_url": "https://cdn.brandfetch.io/idAciuyyPp/w/600/h/600/theme/light/logo.webp"},
    {"keywords": ["bradesco"],                        "name": "Bradesco",             "cor_hex": "#ee032c", "logo_url": "https://cdn.brandfetch.io/idJ-h_LNzX/w/820/h/683/theme/dark/logo.png"},
    {"keywords": ["santander"],                       "name": "Santander",            "cor_hex": "#ea1d25", "logo_url": "https://cdn.brandfetch.io/idex3vA3bq/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["banco do brasil", " bb "],         "name": "Banco do Brasil",      "cor_hex": "#FCFC30", "logo_url": ""},
    {"keywords": ["caixa economica", "caixa federal"], "name": "Caixa Econ\u00f4mica",    "cor_hex": "#F59700", "logo_url": ""},
    {"keywords": [" inter ", "banco inter"],          "name": "Inter",                "cor_hex": "#FF6E07", "logo_url": ""},
    {"keywords": ["c6 bank", "c6bank"],               "name": "C6 Bank",              "cor_hex": "#FFE45C", "logo_url": "https://cdn.brandfetch.io/id9QKeTheX/w/400/h/400/theme/dark/icon.png"},
    {"keywords": ["btg pactual", " btg "],            "name": "BTG Pactual",          "cor_hex": "#195AB4", "logo_url": "https://cdn.brandfetch.io/id2okqRkOi/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["xp investimentos", " xp "],        "name": "XP Investimentos",     "cor_hex": "#ffc60a", "logo_url": ""},
    # Cartoes
    {"keywords": ["american express", "amex"],        "name": "American Express",     "cor_hex": "#006fcf", "logo_url": "https://cdn.brandfetch.io/idgUmCD6wN/w/820/h/820/theme/dark/logo.png"},
    {"keywords": ["mastercard"],                      "name": "Mastercard",           "cor_hex": "#f79e1b", "logo_url": "https://cdn.brandfetch.io/idy21VLzkM/w/180/h/180/theme/dark/logo.png"},
    {"keywords": [" visa "],                          "name": "Visa",                 "cor_hex": "#1a1f71", "logo_url": ""},
    {"keywords": [" elo "],                           "name": "Elo",                  "cor_hex": "#003933", "logo_url": ""},
    # Hoteis
    {"keywords": ["marriott bonvoy", "marriott"],     "name": "Marriott Bonvoy",      "cor_hex": "#FF9962", "logo_url": "https://cdn.brandfetch.io/id0DQ-cAhI/w/360/h/360/theme/dark/icon.png"},
    {"keywords": ["hilton honors", "hilton"],         "name": "Hilton",               "cor_hex": "#0E468B", "logo_url": ""},
    {"keywords": ["world of hyatt", "hyatt"],         "name": "Hyatt",                "cor_hex": "#FFB612", "logo_url": "https://cdn.brandfetch.io/idW8vrk2w-/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["ihg rewards", " ihg "],            "name": "IHG",                  "cor_hex": "#1F4456", "logo_url": ""},
    {"keywords": ["all accor", " accor "],            "name": "Accor ALL",            "cor_hex": "#B88D5B", "logo_url": "https://cdn.brandfetch.io/ido2CWqEYs/w/1980/h/521/theme/light/logo.png"},
    # OTAs / Viagens
    {"keywords": ["booking.com", "booking"],          "name": "Booking.com",          "cor_hex": "#0071C2", "logo_url": ""},
    {"keywords": ["airbnb"],                          "name": "Airbnb",               "cor_hex": "#ff385c", "logo_url": "https://cdn.brandfetch.io/idqFsjQshX/w/76/h/76/theme/dark/logo.png"},
    {"keywords": ["decolar"],                         "name": "Decolar",              "cor_hex": "#550fed", "logo_url": "https://cdn.brandfetch.io/ids1XUQPdz/w/820/h/177/theme/dark/logo.png"},
    {"keywords": ["maxmilhas"],                       "name": "Maxmilhas",            "cor_hex": "#050c16", "logo_url": "https://cdn.brandfetch.io/idVpvUW8tj/w/400/h/400/theme/dark/icon.jpeg"},
]


# A API do OpenAI /images/edits NAO aceita SVG/GIF — filtramos na fonte.
_SUPPORTED_LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _is_supported_logo(url: str) -> bool:
    if not url:
        return False
    lower = url.lower().split("?", 1)[0]
    return lower.endswith(_SUPPORTED_LOGO_EXTS)


def _keyword_from_brand(marca: str, dominio: str) -> list[str]:
    """Gera keywords default a partir do nome da marca e dominio."""
    kws: list[str] = []
    marca = (marca or "").strip()
    dominio = (dominio or "").strip().lower()
    if marca:
        kws.append(marca.lower())
    if dominio:
        root = dominio.split("/")[0].split(".")[0]
        if root and root not in {kw.replace(" ", "") for kw in kws}:
            kws.append(root)
    return [k for k in kws if k]


def _merge_catalogs(base: list[dict], extra: list[dict]) -> list[dict]:
    """Mescla catalogos priorizando ``base`` (keywords curadas).

    Para cada marca do ``extra``, se ja existir no ``base`` (match por nome
    normalizado), preenchemos ``logo_url``/``cor_hex`` faltantes. Se nao
    existir, acrescentamos ao final.
    """
    by_name = {b["name"].lower(): b for b in base}
    merged = [dict(b) for b in base]
    merged_by_name = {m["name"].lower(): m for m in merged}
    for row in extra:
        existing = by_name.get(row["name"].lower())
        if existing:
            target = merged_by_name[existing["name"].lower()]
            for key in ("cor_hex", "logo_url"):
                if not target.get(key) and row.get(key):
                    target[key] = row[key]
            for kw in row.get("keywords", []):
                if kw and kw not in target["keywords"]:
                    target["keywords"].append(kw)
        else:
            merged.append(dict(row))
            merged_by_name[row["name"].lower()] = merged[-1]
    return merged


def _load_from_db() -> list[dict]:
    """Consulta ``MarcaCatalogo`` (ativos) e normaliza para o formato esperado.

    Retorna lista vazia se a tabela nao existir, estiver vazia, ou o app
    ainda nao estiver pronto (bootstrap).
    """
    try:
        from django.apps import apps

        if not apps.ready:
            return []
        MarcaCatalogo = apps.get_model("gestao", "MarcaCatalogo")
    except Exception as exc:  # pragma: no cover
        logger.debug("BRAND_CATALOG: apps nao prontos (%s)", exc)
        return []

    try:
        rows: list[dict] = []
        for m in MarcaCatalogo.objects.filter(ativo=True).order_by("id"):
            kws = list(m.keywords) if isinstance(m.keywords, list) else []
            if not kws:
                kws = _keyword_from_brand(m.nome, m.dominio)
            if not kws:
                continue
            logo_url = m.logo_url or ""
            rows.append({
                "keywords": kws,
                "name": m.nome,
                "cor_hex": m.cor_hex or "#000000",
                "logo_url": logo_url if _is_supported_logo(logo_url) else "",
            })
        return rows
    except Exception as exc:
        logger.warning("BRAND_CATALOG: falha consultando MarcaCatalogo: %s", exc)
        return []


@lru_cache(maxsize=1)
def load_brand_catalog() -> list[dict]:
    """Carrega o catalogo de marcas.

    Prioridade:
      1. ``MarcaCatalogo`` no banco (mesclado com o fallback curado).
      2. ``_FALLBACK_BRAND_CATALOG`` hardcoded quando o DB esta vazio.

    Cacheado via ``lru_cache``. Para forcar reload (ex.: apos reimportar
    o CSV), chame ``load_brand_catalog.cache_clear()``.
    """
    db_rows = _load_from_db()
    if db_rows:
        return _merge_catalogs(_FALLBACK_BRAND_CATALOG, db_rows)
    logger.info("BRAND_CATALOG: usando fallback hardcoded (MarcaCatalogo vazia/indisponivel)")
    return list(_FALLBACK_BRAND_CATALOG)
