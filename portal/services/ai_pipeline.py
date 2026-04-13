from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
import hashlib
import json
import os
from pathlib import Path
import re
import textwrap
from typing import Any
import unicodedata
from uuid import uuid4
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.defaultfilters import slugify
from django.utils import timezone


_SYSTEM_PROMPT_REWRITE = (
    "Você é editor-chefe de um portal premium de milhas, cartões e viagens. "
    "Seu público são viajantes e investidores em programas de fidelidade.\n\n"

    "## TAREFA\n"
    "Reescreva o artigo para ser completamente original. Não copie trechos. "
    "Responda em JSON estruturado com 13 campos obrigatórios.\n\n"

    "## PROCESSO\n"
    "1. Identifique o tipo de conteúdo: é notícia de promoção com prazo? análise? guia?\n"
    "2. Escolha categoria com base no tipo (não em keywords aleatórias)\n"
    "3. Escreva texto original mantendo fatos exatos (datas, %, valores, nomes)\n"
    "4. Revise para PT-BR correto antes de gerar JSON\n\n"

    "## REGRAS DE CATEGORIZAÇÃO\n"
    "- PROMOÇÕES: tem prazo, bônus temporário, oferta com data-limite (mesmo se envolve viagem/hotel)\n"
    "- MILHAS E PONTOS: transferências/programas sem prazo, emissões, resgates\n"
    "- CARTÕES DE CRÉDITO: análises, lançamentos, bônus adesão, anuidade, aprovação\n"
    "- HOTÉIS E RESORTS: programas hoteleiros, hospedagem com pontos (sem prazo especial)\n"
    "- VIAGENS: editorial puro (destinos, roteiros, guias, cruzeiros) — NUNCA para promoção com prazo\n\n"

    "## ESTRUTURA DE TEXTO\n"
    "- Parágrafo 1: responda a pergunta principal do leitor (tipo FAQ/snippet)\n"
    "- Corpo: 3-6 parágrafos com contexto, detalhes práticos, restrições importantes\n"
    "- Feche com valor real ou próximos passos\n"
    "- Sem 'traços isolados' (- ) no meio de frases\n"
    "- Sem tom robótico\n\n"

    "## CAMPOS JSON\n"
    "- titulo: até 220 caracteres, sem asteriscos\n"
    "- resumo: até 280 caracteres, até 2 frases, sem asteriscos\n"
    "- conteudo: corpo completo em markdown, use **palavra** raramente (só termos-chave)\n"
    "- seo_title: 60-68 chars, com palavra-chave principal, sem asteriscos\n"
    "- meta_description: 150-160 chars, complementa seo_title, sem asteriscos\n"
    "- confianca: 0.0 a 1.0 (0.85+ = fatos verificados, 0.50 = parcialmente claro, 0.30 = especulativo)\n"
    "- cta_url: URL da melhor ação (oferta oficial, regulamento). Vazio se não houver.\n"
    "- cta_label: rótulo de CTA (máx 40 chars). Vazio se cta_url vazio.\n"
    "- tags: até 5 tags (marcas, programas, tópicos principais)\n"
    "- slug: lowercase com hífens, até 220 chars\n"
    "- topico: subcategoria editorial\n"
    "- imagem_prompt: descrição 2-3 linhas de cena visual que capture o tema, "
    "com estilo fotorrealístico ou ilustração moderna, composição clean, sem textos ou watermarks\n"
    "- categoria: uma das 5 categorias acima\n\n"

    "## CHECKLIST ANTES DE RESPONDER\n"
    "✓ Nenhum trecho copiado da fonte\n"
    "✓ Fatos numéricos exatos (datas, %, valores)\n"
    "✓ Acentuação e ortografia PT-BR\n"
    "✓ Restrições e público elegível mencionados\n"
    "✓ Categoria justificada pela lógica acima\n"
    "✓ Meta-description diferente do título\n"
    "✓ JSON válido e completo"
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_IMAGES_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
OPENAI_IMAGES_EDITS_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_NEWS_MODEL = os.environ.get("OPENAI_NEWS_MODEL", "gpt-5.4")
DEFAULT_IMAGE_MODEL = os.environ.get("OPENAI_NEWS_IMAGE_MODEL", "gpt-image-1.5")
DEFAULT_CONFIDENCE_THRESHOLD = Decimal(os.environ.get("PORTAL_NEWS_CONFIDENCE_THRESHOLD", "0.70"))
PUBLIC_SITE_FOR_BOT = (os.environ.get("SITE_BASE_URL") or "https://ncfly.com.br").strip().rstrip("/") or "https://ncfly.com.br"
DEFAULT_BOT_USER_AGENT = f"Mozilla/5.0 (compatible; NCFlyBot/1.0; +{PUBLIC_SITE_FOR_BOT})"

TOPIC_RULES = {
    "Milhas e Pontos": {
        "default": "Programas de Fidelidade",
        "topics": {
            "Transferências Bonificadas": (
                "transferencia bonificada",
                "transferencias bonificadas",
                "transferencia",
                "bonus",
                "bonificada",
            ),
            "Programas de Fidelidade": (
                "programa de fidelidade",
                "programas de fidelidade",
                "latam pass",
                "smiles",
                "livelo",
                "azul fidelidade",
                "esfera",
                "programa",
                "fidelidade",
            ),
            "Emissões e Resgates": (
                "emissao",
                "emissoes",
                "resgate",
                "resgates",
                "passagem premio",
                "emitir",
                "resgatar",
            ),
            "Clubes e Assinaturas": (
                "clube",
                "assinatura",
                "mensalidade",
                "renovacao",
            ),
            "Salas VIP e Benefícios": (
                "sala vip",
                "salas vip",
                "priority pass",
                "dragon pass",
                "lounge",
                "beneficio",
            ),
            "Compra e Venda de Pontos": (
                "compra de pontos",
                "comprar pontos",
                "venda de milhas",
                "milhas",
            ),
        },
    },
    "Cartões de Crédito": {
        "default": "Lançamentos e Análises",
        "topics": {
            "Lançamentos e Análises": (
                "lancamento",
                "novo cartao",
                "review",
                "analise",
                "avaliacao",
            ),
            "Bônus de Adesão": (
                "bonus de adesao",
                "welcome bonus",
                "bonus",
                "campanha de adesao",
            ),
            "Salas VIP e Benefícios": (
                "sala vip",
                "salas vip",
                "lounge",
                "priority pass",
                "beneficio",
            ),
            "Anuidade e Isenção": (
                "anuidade",
                "isencao",
                "isenção",
                "desconto",
                "mensalidade",
            ),
            "Aprovação e Renda": (
                "aprovacao",
                "aprovação",
                "renda minima",
                "renda",
                "score",
                "limite",
            ),
        },
    },
    "Hotéis e Resorts": {
        "default": "Programas Hoteleiros",
        "topics": {
            "Programas Hoteleiros": (
                "marriott",
                "hilton",
                "hyatt",
                "ihg",
                "accor",
                "programa hoteleiro",
            ),
            "Hospedagem com Pontos": (
                "hospedagem com pontos",
                "resgate",
                "diarias com pontos",
                "award stay",
                "resort credit",
            ),
            "Resorts e Experiências": (
                "resort",
                "all inclusive",
                "experiencia",
                "experiencias",
                "luxo",
            ),
            "Destinos e Guias": (
                "destino",
                "guia",
                "roteiro",
                "cidade",
                "praia",
            ),
            "Promoções de Hospedagem": (
                "promocao",
                "promocoes",
                "desconto",
                "diaria",
                "cupom",
            ),
        },
    },
    "Promoções": {
        "default": "Ofertas Relâmpago",
        "topics": {
            "Transferências e Bônus": (
                "transferencia",
                "bonus",
                "bonificada",
                "campanha",
            ),
            "Passagens Aéreas": (
                "passagem",
                "passagens",
                "voo",
                "tarifa",
                "aereo",
            ),
            "Hotéis e Resorts": (
                "hotel",
                "hoteis",
                "resort",
                "hospedagem",
            ),
            "Cartões e Cashback": (
                "cartao",
                "cartoes",
                "cashback",
                "anuidade",
            ),
            "Ofertas Relâmpago": (
                "oferta",
                "ofertas",
                "desconto",
                "cupom",
                "relampago",
            ),
        },
    },
    "Viagens": {
        "default": "Destinos e Roteiros",
        "topics": {
            "Destinos e Roteiros": (
                "destino",
                "roteiro",
                "viagem",
                "viagens",
                "turismo",
                "guia",
            ),
            "Passagens e Voos": (
                "passagem",
                "passagens",
                "voo",
                "voos",
                "aereo",
                "aeroporto",
                "companhia aerea",
            ),
            "Hospedagem": (
                "hotel",
                "hoteis",
                "resort",
                "hospedagem",
                "pousada",
                "airbnb",
            ),
            "Dicas de Viagem": (
                "dica",
                "dicas",
                "bagagem",
                "seguro viagem",
                "check-in",
                "embarque",
                "lounge",
            ),
            "Cruzeiros e Pacotes": (
                "cruzeiro",
                "pacote",
                "pacotes",
                "tour",
                "excursao",
            ),
        },
    },
}

KNOWN_TAGS = (
    "LATAM Pass",
    "Smiles",
    "Azul Fidelidade",
    "Livelo",
    "Esfera",
    "Mastercard Black",
    "Visa Infinite",
    "American Express",
    "Cashback",
    "Sala VIP",
    "Priority Pass",
    "Dragon Pass",
    "Marriott Bonvoy",
    "Hilton Honors",
    "Accor Live Limitless",
    "Iberia Plus",
    "Executive Club",
    "Bônus",
    "Transferência",
    "Promoção",
)


BRAND_COVER_THEMES = (
    {
        "label": "Azul Viagens",
        "aliases": ("azul viagens", "azul fidelidade", "tudoazul", "azul"),
        "hint": "Marca em destaque",
        "background_start": "#032b6b",
        "background_mid": "#1357c5",
        "background_end": "#17a6ff",
        "wordmark_color": "#ffffff",
        "accent_color": "#ffb703",
    },
    {
        "label": "Livelo",
        "aliases": ("livelo",),
        "hint": "Programa em destaque",
        "background_start": "#23135f",
        "background_mid": "#5c2dd5",
        "background_end": "#c54ac9",
        "wordmark_color": "#ffffff",
        "accent_color": "#4fe0c3",
    },
    {
        "label": "Smiles",
        "aliases": ("smiles",),
        "hint": "Programa em destaque",
        "background_start": "#722100",
        "background_mid": "#ff6a00",
        "background_end": "#ffb347",
        "wordmark_color": "#ffffff",
        "accent_color": "#fff1b8",
    },
    {
        "label": "LATAM Pass",
        "aliases": ("latam pass", "latampass", "latam"),
        "hint": "Programa em destaque",
        "background_start": "#1a1f71",
        "background_mid": "#5f2dbf",
        "background_end": "#df2c6e",
        "wordmark_color": "#ffffff",
        "accent_color": "#ffb3c7",
    },
    {
        "label": "Esfera",
        "aliases": ("esfera",),
        "hint": "Programa em destaque",
        "background_start": "#4d0019",
        "background_mid": "#a80d44",
        "background_end": "#ff5b87",
        "wordmark_color": "#ffffff",
        "accent_color": "#ffd8e5",
    },
    {
        "label": "TAP",
        "aliases": ("tap air portugal", "tap portugal", "tap"),
        "hint": "Companhia em destaque",
        "background_start": "#044c3f",
        "background_mid": "#0a8b65",
        "background_end": "#cf102d",
        "wordmark_color": "#ffffff",
        "accent_color": "#f4d35e",
    },
    {
        "label": "BTG",
        "aliases": ("btg pactual", "btg"),
        "hint": "Banco em destaque",
        "background_start": "#041d5b",
        "background_mid": "#0e49c7",
        "background_end": "#2db9ff",
        "wordmark_color": "#ffffff",
        "accent_color": "#9ee7ff",
    },
    {
        "label": "C6",
        "aliases": ("c6 bank", "c6"),
        "hint": "Banco em destaque",
        "background_start": "#111111",
        "background_mid": "#2a2a2a",
        "background_end": "#b6923a",
        "wordmark_color": "#ffffff",
        "accent_color": "#f7d57a",
    },
    {
        "label": "XP",
        "aliases": ("xp investimentos", "xp"),
        "hint": "Banco em destaque",
        "background_start": "#111111",
        "background_mid": "#2f2f2f",
        "background_end": "#f7a400",
        "wordmark_color": "#ffffff",
        "accent_color": "#ffe3a3",
    },
    {
        "label": "Mastercard Black",
        "aliases": ("mastercard black", "master black"),
        "hint": "Cartao em destaque",
        "background_start": "#050505",
        "background_mid": "#1c1c1c",
        "background_end": "#d94c2a",
        "wordmark_color": "#ffffff",
        "accent_color": "#ffb06b",
    },
    {
        "label": "Visa Infinite",
        "aliases": ("visa infinite",),
        "hint": "Cartao em destaque",
        "background_start": "#091f57",
        "background_mid": "#1a4dcc",
        "background_end": "#67b2ff",
        "wordmark_color": "#ffffff",
        "accent_color": "#d8efff",
    },
    {
        "label": "American Express",
        "aliases": ("american express", "amex"),
        "hint": "Cartao em destaque",
        "background_start": "#0057b8",
        "background_mid": "#1583ff",
        "background_end": "#7ddcff",
        "wordmark_color": "#ffffff",
        "accent_color": "#dff8ff",
    },
)


GENERIC_COVER_PALETTES = (
    {
        "background_start": "#0f172a",
        "background_mid": "#1d4ed8",
        "background_end": "#38bdf8",
        "wordmark_color": "#ffffff",
        "accent_color": "#bfdbfe",
    },
    {
        "background_start": "#1f2937",
        "background_mid": "#7c3aed",
        "background_end": "#d946ef",
        "wordmark_color": "#ffffff",
        "accent_color": "#f5d0fe",
    },
    {
        "background_start": "#111827",
        "background_mid": "#f97316",
        "background_end": "#facc15",
        "wordmark_color": "#ffffff",
        "accent_color": "#fef3c7",
    },
    {
        "background_start": "#0b132b",
        "background_mid": "#0ea5a4",
        "background_end": "#34d399",
        "wordmark_color": "#ffffff",
        "accent_color": "#d1fae5",
    },
)


_COMPOSITE_BRAND_LABEL_PATTERNS = (
    re.compile(
        r"\b(xp|btg(?:\s+pactual)?|c6(?:\s+bank)?)\s+"
        r"(visa\s+infinite|mastercard\s+black|american\s+express|amex)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(visa\s+infinite|mastercard\s+black|american\s+express|amex)\s+"
        r"(?:do|da|de)\s+"
        r"(xp|btg(?:\s+pactual)?|c6(?:\s+bank)?)\b",
        re.IGNORECASE,
    ),
)


_GENERIC_BRAND_LABEL_PATTERNS = (
    re.compile(
        r"\b(?:cartao|cartao|cart[aã]o|programa|clube|banco|campanha|promocao|promo[cç][aã]o|oferta|aniversario)\s+"
        r"(?:da|do|de|na|no|com)?\s*"
        r"([a-z0-9&.+-]+(?:\s+[a-z0-9&.+-]+){0,4})",
        re.IGNORECASE,
    ),
)


_BRAND_LABEL_TOKEN_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "ate",
    "até",
    "beneficio",
    "beneficios",
    "benefício",
    "benefícios",
    "bonus",
    "bônus",
    "card",
    "cartao",
    "cartão",
    "clientes",
    "clube",
    "com",
    "compra",
    "conta",
    "desconto",
    "e",
    "em",
    "empresa",
    "entrega",
    "especial",
    "garante",
    "gratis",
    "grátis",
    "hotel",
    "hoteis",
    "hotéis",
    "libera",
    "milhas",
    "na",
    "nas",
    "nc",
    "news",
    "no",
    "nos",
    "nova",
    "novo",
    "oferece",
    "pacote",
    "pacotes",
    "para",
    "passagens",
    "pontos",
    "premio",
    "prêmio",
    "programa",
    "promocao",
    "promoção",
    "smiles",
    "sua",
    "suas",
    "trecho",
    "valida",
    "viagem",
    "viagens",
}


_BRAND_TOKEN_CANONICAL = {
    "accor": "Accor",
    "all": "ALL",
    "amex": "Amex",
    "american": "American",
    "avios": "Avios",
    "azul": "Azul",
    "bank": "Bank",
    "black": "Black",
    "bonvoy": "Bonvoy",
    "bradesco": "Bradesco",
    "btg": "BTG",
    "c6": "C6",
    "caixa": "Caixa",
    "club": "Club",
    "executive": "Executive",
    "esfera": "Esfera",
    "express": "Express",
    "fidelidade": "Fidelidade",
    "gol": "Gol",
    "honors": "Honors",
    "iberia": "Iberia",
    "infinite": "Infinite",
    "inter": "Inter",
    "itau": "Itau",
    "itaucard": "Itaucard",
    "latam": "LATAM",
    "livelo": "Livelo",
    "mastercard": "Mastercard",
    "miles": "Miles",
    "more": "More",
    "pass": "Pass",
    "pactual": "Pactual",
    "plus": "Plus",
    "porto": "Porto",
    "santander": "Santander",
    "smiles": "Smiles",
    "tap": "TAP",
    "tudoazul": "TudoAzul",
    "visa": "Visa",
    "viagens": "Viagens",
    "xp": "XP",
}


@dataclass
class NewsDraft:
    titulo: str
    resumo: str
    conteudo: str
    categoria: str
    topico: str
    tags: list[str]
    cta_url: str
    cta_label: str
    slug: str
    confianca: Decimal
    seo_title: str = ""
    meta_description: str = ""
    imagem_url: str = ""
    imagem_ilustrativa: bool = False
    imagem_prompt: str = ""
    metadata: dict[str, Any] | None = None


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).lower() in {"1", "true", "yes", "on"}


def _get_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")
    return api_key


def _openai_json_request(url: str, payload: dict) -> dict:
    api_key = _get_openai_api_key()
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _openai_request(payload: dict) -> dict:
    return _openai_json_request(OPENAI_RESPONSES_URL, payload)


def _extract_response_text(response_json: dict) -> str:
    if response_json.get("output_text"):
        return response_json["output_text"]
    output = response_json.get("output", []) or []
    parts: list[str] = []
    for item in output:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _normalize_category(value: str) -> str:
    # Normaliza sem acentos para comparação robusta
    raw = (value or "").strip()
    normalized = _normalize_lookup(raw)
    mapping = {
        # Milhas e Pontos
        "milhas": "Milhas e Pontos",
        "milhas e pontos": "Milhas e Pontos",
        "pontos": "Milhas e Pontos",
        "fidelidade": "Milhas e Pontos",
        # Cartões de Crédito
        "cartoes": "Cartões de Crédito",
        "cartoes de credito": "Cartões de Crédito",
        "cartoes de credito": "Cartões de Crédito",
        "cartao de credito": "Cartões de Crédito",
        "credito": "Cartões de Crédito",
        # Hotéis e Resorts
        "hoteis": "Hotéis e Resorts",
        "hoteis e resorts": "Hotéis e Resorts",
        "resorts": "Hotéis e Resorts",
        "hotel": "Hotéis e Resorts",
        # Promoções
        "promocoes": "Promoções",
        "promocao": "Promoções",
        "promocoes e ofertas": "Promoções",
        "ofertas": "Promoções",
        # Viagens
        "viagens": "Viagens",
        "viagem": "Viagens",
        "turismo": "Viagens",
        "destinos": "Viagens",
        "destino": "Viagens",
        "roteiro": "Viagens",
        "roteiros": "Viagens",
    }
    return mapping.get(normalized, "Milhas e Pontos")


def _normalize_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


def _repair_text_artifacts(value: str) -> str:
    text = value or ""
    replacements = {
        "Ã¡": "á",
        "Ã¢": "â",
        "Ã£": "ã",
        "Ã©": "é",
        "Ãª": "ê",
        "Ã­": "í",
        "Ã³": "ó",
        "Ã´": "ô",
        "Ãµ": "õ",
        "Ãº": "ú",
        "Ã§": "ç",
        "Â°": "°",
        "â€¢": "•",
        "â€“": "–",
        "â€”": "—",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
    }
    for broken, fixed in replacements.items():
        text = text.replace(broken, fixed)
    return text


def _normalize_topic(category: str, value: str, title: str = "", summary: str = "", body: str = "") -> str:
    canonical_category = _normalize_category(category)
    rules = TOPIC_RULES.get(canonical_category, {})
    topic_map = rules.get("topics", {})
    normalized_value = _normalize_lookup(value)

    if normalized_value:
        for label, keywords in topic_map.items():
            normalized_candidates = {_normalize_lookup(label), *(_normalize_lookup(keyword) for keyword in keywords)}
            if normalized_value in normalized_candidates:
                return label

    haystack = _normalize_lookup(" ".join(filter(None, [title, summary, body[:1200]])))
    best_label = rules.get("default", "Panorama do Setor")
    best_score = 0
    for label, keywords in topic_map.items():
        score = 0
        for keyword in keywords:
            normalized_keyword = _normalize_lookup(keyword)
            if normalized_keyword and normalized_keyword in haystack:
                score += haystack.count(normalized_keyword)
        if score > best_score:
            best_label = label
            best_score = score
    return best_label


def _normalize_tags(tags: list[str] | tuple[str, ...] | str | None, category: str, topic: str, title: str, summary: str, body: str) -> list[str]:
    raw_items: list[str] = []
    if isinstance(tags, str):
        raw_items.extend(part.strip() for part in re.split(r"[,;|]", tags) if part.strip())
    elif isinstance(tags, (list, tuple)):
        raw_items.extend(str(item).strip() for item in tags if str(item).strip())

    haystack = _normalize_lookup(" ".join(filter(None, [title, summary, body[:800]])))
    for known_tag in KNOWN_TAGS:
        if _normalize_lookup(known_tag) in haystack:
            raw_items.append(known_tag)

    raw_items.insert(0, topic)
    raw_items.insert(0, category)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        clean_item = " ".join(str(item).split()).strip()
        if not clean_item:
            continue
        key = _normalize_lookup(clean_item)
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(clean_item[:40])
        if len(normalized) >= 5:
            break
    return normalized


def _clean_generated_text(value: str) -> str:
    text = _repair_text_artifacts((value or "").replace("\r", "").strip())
    parts = []
    for chunk in re.split(r"\n{2,}", text):
        line = " ".join(chunk.split()).strip()
        if not line:
            continue
        lowered = line.lower()
        if any(
            marker in lowered
            for marker in (
                "filtrar por",
                "ver todos",
                "publicidade",
                "deixe um comentário",
                "deixe um comentario",
                "notícias relacionadas",
                "noticias relacionadas",
                "fonte original",
            )
        ):
            continue
        parts.append(line)
    return "\n\n".join(parts)


def _build_cover_focus_prompt(title: str, summary: str, category: str) -> str:
    label = _extract_cover_brand_label(title, summary, category)
    lowered = _normalize_lookup(f"{title} {summary}")
    instructions: list[str] = []

    if label:
        instructions.append(
            f"Priorize um único elemento hero claramente ligado a {label}, com identidade visual reconhecível e protagonismo na composição."
        )
        instructions.append(
            f"Se houver marcas, programas, cartões, companhias ou aeronaves relacionados a {label}, mantenha o foco neles e evite dispersar a cena em muitos assuntos ao mesmo tempo."
        )

    if any(keyword in lowered for keyword in ("promocode", "cupom", "coupon", "% off", "desconto")):
        instructions.append(
            "Se a pauta envolver cupom, promocode ou desconto, represente isso com um único elemento visual de voucher, ticket ou selo promocional discreto e elegante."
        )

    instructions.append(
        "Evite colagens genéricas com excesso de malas, carros, ônibus, balões, presentes, hotéis ou vários objetos ao mesmo tempo, a menos que sejam essenciais para entender a pauta."
    )
    instructions.append(
        "Prefira uma direção de arte mais limpa, com poucos elementos fortes, boa hierarquia visual e cara de capa editorial premium."
    )

    return " ".join(instructions)


def _build_cover_prompt(title: str, summary: str, category: str) -> str:
    return (
        f"Capa editorial premium para uma notícia de {category}. "
        f"Tema principal: {title}. "
        f"Contexto: {summary[:220]}. "
        "A imagem deve manter a mesma ideia editorial central da matéria, com os mesmos produtos, marcas, programas, companhias, cartões, aeronaves ou destinos quando forem parte essencial da notícia. "
        "Pode mostrar logos, marcas e produtos reais de forma contextual e jornalística, se isso fizer sentido para o tema. "
        "A composição final deve ser uma nova variação visual, não uma cópia da capa vista no site de referência. "
        "Altere enquadramento, perspectiva, crop, distribuição dos elementos, distância da câmera, profundidade, proporção entre objetos, luz, textura e pequenos detalhes visuais. "
        "O resultado pode lembrar a mesma campanha ou assunto, mas não deve reproduzir exatamente a arte promocional original. "
        f"{_build_cover_focus_prompt(title, summary, category)} "
        "Estilo fotorrealístico ou ilustração moderna, composição clean com poucos elementos fortes e boa hierarquia visual. "
        "Visual sofisticado, com cara de capa de portal premium. Sem texto, sem marcas d'água, sem interface, sem branding do site-fonte."
    )


def _build_cover_reference_prompt(title: str, summary: str, category: str) -> str:
    return (
        f"Edite a imagem de referência para criar uma nova capa editorial premium de {category}. "
        f"Tema principal: {title}. "
        f"Contexto: {summary[:220]}. "
        "Mantenha a mesma ideia central, os mesmos produtos, marcas, programas, companhias, cartões, aeronaves ou destinos que forem relevantes na matéria. "
        "A nova capa deve continuar reconhecível em relação ao tema original, mas com alterações controladas no enquadramento, crop, perspectiva, organização dos elementos, luz, profundidade, textura e pequenos detalhes. "
        "Não copie a arte exatamente como está. Gere uma variação editorial refinada e própria, como se fosse uma nova versão da mesma campanha ou assunto. "
        f"{_build_cover_focus_prompt(title, summary, category)} "
        "Sem texto adicional, sem marcas d'água, sem interface, sem branding do site-fonte."
    )


def _guess_image_mime_type(image_url: str, content_type: str = "") -> str:
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type.startswith("image/"):
        return normalized_content_type
    lowered = (image_url or "").lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    if lowered.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def _build_reference_image_data_url(image_url: str) -> str:
    request = Request(
        image_url,
        headers={
            "User-Agent": DEFAULT_BOT_USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        image_bytes = response.read()
        content_type = getattr(response, "headers", {}).get("Content-Type", "")
    mime_type = _guess_image_mime_type(image_url, content_type)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _download_reference_image(image_url: str) -> tuple[bytes, str]:
    request = Request(
        image_url,
        headers={
            "User-Agent": DEFAULT_BOT_USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        image_bytes = response.read()
        content_type = getattr(response, "headers", {}).get("Content-Type", "")
    mime_type = _guess_image_mime_type(image_url, content_type)
    return image_bytes, mime_type


def _mime_type_to_extension(mime_type: str) -> str:
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    return mapping.get((mime_type or "").lower(), "jpg")


def _build_multipart_form_data(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----NCFlyBoundary{uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    for field_name, filename, file_bytes, mime_type in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                file_bytes,
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def _openai_multipart_request(url: str, fields: list[tuple[str, str]], files: list[tuple[str, str, bytes, str]]) -> dict:
    api_key = _get_openai_api_key()
    body, boundary = _build_multipart_form_data(fields, files)
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _openai_image_generation_request(prompt: str) -> dict:
    payload = {
        "model": DEFAULT_IMAGE_MODEL,
        "prompt": prompt,
        "size": "1536x1024",
        "quality": "medium",
    }
    return _openai_json_request(OPENAI_IMAGES_GENERATIONS_URL, payload)


def _openai_image_edit_request(prompt: str, reference_image_url: str) -> dict:
    image_bytes, mime_type = _download_reference_image(reference_image_url)
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"Tipo de imagem de referencia nao suportado para edicao: {mime_type}")

    fields = [
        ("model", DEFAULT_IMAGE_MODEL),
        ("prompt", prompt),
        ("size", "1536x1024"),
        ("quality", "medium"),
    ]
    files = [
        (
            "image",
            f"reference.{_mime_type_to_extension(mime_type)}",
            image_bytes,
            mime_type,
        )
    ]
    return _openai_multipart_request(OPENAI_IMAGES_EDITS_URL, fields, files)


def _extract_generated_image_bytes(response_json: dict) -> bytes | None:
    data = response_json.get("data") or []
    if not data:
        return None

    first = data[0] or {}
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"])

    if first.get("url"):
        request = Request(
            first["url"],
            headers={"User-Agent": DEFAULT_BOT_USER_AGENT},
        )
        with urlopen(request, timeout=60) as response:
            return response.read()

    return None


def _normalize_cta(url: str, label: str, outbound_links: list[dict] | None) -> tuple[str, str]:
    cleaned_url = (url or "").strip()
    cleaned_label = " ".join((label or "").split()).strip()
    available_links = outbound_links or []
    available_urls = {item.get("url", "").strip(): item for item in available_links if isinstance(item, dict)}

    if cleaned_url and cleaned_url in available_urls:
        if not cleaned_label:
            cleaned_label = available_urls[cleaned_url].get("label", "")
        return cleaned_url, (cleaned_label or "Ir para a oferta")[:80]

    if available_links:
        best = available_links[0]
        return best.get("url", "").strip(), (" ".join((best.get("label") or "").split()).strip() or "Ir para a oferta")[:80]

    return "", ""


def _normalize_confidence(value: Decimal | str | float | int | None) -> Decimal:
    try:
        confidence = Decimal(str(value if value is not None else "0.40"))
    except Exception:
        confidence = Decimal("0.40")
    if confidence > 1 and confidence <= 10:
        confidence = confidence / Decimal("10")
    if confidence < 0:
        confidence = Decimal("0.00")
    if confidence > 1:
        confidence = Decimal("1.00")
    return confidence.quantize(Decimal("0.01"))


def _truncate_clean_text(value: str, limit: int) -> str:
    cleaned = " ".join(_repair_text_artifacts(value or "").split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[:limit].rsplit(" ", 1)[0].strip()
    return clipped or cleaned[:limit].strip()


def _normalize_seo_title(title: str, seo_title: str = "") -> str:
    return _truncate_clean_text(seo_title or title, 68)


def _normalize_meta_description(summary: str, content: str, meta_description: str = "") -> str:
    base = meta_description or summary or content
    return _truncate_clean_text(base, 158)


def _apply_quality_rules(draft: NewsDraft, raw_article: dict) -> NewsDraft:
    titulo = " ".join(_repair_text_artifacts(draft.titulo or raw_article.get("titulo_extraido") or "").split()).strip()
    resumo = " ".join(_repair_text_artifacts(draft.resumo or raw_article.get("resumo_base") or "").split()).strip()
    conteudo = _clean_generated_text(draft.conteudo or raw_article.get("texto_base") or "")
    categoria = _normalize_category(draft.categoria or raw_article.get("categoria_padrao") or "")
    topico = _normalize_topic(
        categoria,
        draft.topico,
        titulo,
        resumo,
        conteudo,
    )
    tags = _normalize_tags(draft.tags, categoria, topico, titulo, resumo, conteudo)
    cta_url, cta_label = _normalize_cta(draft.cta_url, draft.cta_label, raw_article.get("outbound_links"))
    slug = (draft.slug or slugify(titulo))[:220]
    confianca = _normalize_confidence(draft.confianca or "0.40")
    seo_title = _normalize_seo_title(titulo, draft.seo_title)
    meta_description = _normalize_meta_description(resumo, conteudo, draft.meta_description)
    quality_flags: list[str] = []

    if len(titulo) < 18:
        quality_flags.append("titulo_curto")
        confianca = min(confianca, Decimal("0.55"))
    if len(resumo) < 90:
        fallback_summary = (raw_article.get("resumo_base") or raw_article.get("texto_base") or resumo)[:240]
        resumo = fallback_summary.rsplit(" ", 1)[0] if " " in fallback_summary else fallback_summary
        quality_flags.append("resumo_recomposto")
        confianca = min(confianca, Decimal("0.65"))
    if len(conteudo) < 500:
        quality_flags.append("conteudo_curto")
        confianca = min(confianca, Decimal("0.55"))
    if any(marker in conteudo.lower() for marker in ("filtrar por", "ver todos", "publicidade")):
        quality_flags.append("conteudo_com_ruido")
        confianca = min(confianca, Decimal("0.40"))

    metadata = dict(draft.metadata or {})
    metadata["editorial_classification"] = {
        "categoria": categoria,
        "topico": topico,
        "tags": tags,
    }
    metadata["seo"] = {
        "title": seo_title,
        "meta_description": meta_description,
        "keywords": tags,
    }
    if cta_url:
        metadata["offer_cta"] = {
            "url": cta_url,
            "label": cta_label or "Ir para a oferta",
        }
    if quality_flags:
        metadata["quality_flags"] = quality_flags

    return NewsDraft(
        titulo=titulo[:220],
        resumo=resumo[:280],
        conteudo=conteudo,
        categoria=categoria,
        topico=topico,
        tags=tags,
        cta_url=cta_url,
        cta_label=cta_label,
        slug=slug,
        confianca=confianca,
        seo_title=seo_title,
        meta_description=meta_description,
        imagem_url=draft.imagem_url,
        imagem_ilustrativa=draft.imagem_ilustrativa,
        imagem_prompt=draft.imagem_prompt or _build_cover_prompt(titulo, resumo, categoria),
        metadata=metadata,
    )


NEWS_JSON_FIELDS = (
    "titulo, resumo, conteudo, categoria, topico, tags, cta_url, cta_label, "
    "slug, confianca, seo_title, meta_description, imagem_prompt"
)


def _build_news_system_prompt(*, schema_mode: bool) -> str:
    output_rule = (
        "Responda apenas com o JSON aceito pelo schema informado. Não inclua texto fora do JSON."
        if schema_mode
        else f"Responda apenas com JSON válido contendo exatamente estes campos: {NEWS_JSON_FIELDS}. Não inclua texto fora do JSON."
    )
    return f"{_SYSTEM_PROMPT_REWRITE}\n\n{output_rule}"


def _build_news_user_prompt(source_name: str, raw_article: dict) -> str:
    return textwrap.dedent(
        f"""
        Fonte: {source_name}
        URL original: {raw_article.get('url_original')}
        Titulo base: {raw_article.get('titulo_extraido')}
        Data atual: {timezone.localdate().isoformat()}
        Data base: {raw_article.get('data_publicacao_original')}
        Resumo base: {raw_article.get('resumo_base')}
        Categoria sugerida pela fonte: {raw_article.get('categoria_padrao')}
        Links externos relevantes:
        {json.dumps(raw_article.get('outbound_links') or [], ensure_ascii=False)}

        Texto base:
        {raw_article.get('texto_base')}
        """
    ).strip()


def _rewrite_with_openai_schema(source_name: str, raw_article: dict) -> NewsDraft:
    payload = {
        "model": DEFAULT_NEWS_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_news_system_prompt(schema_mode=True),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_news_user_prompt(source_name, raw_article),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "portal_news_article",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "titulo": {"type": "string"},
                        "resumo": {"type": "string"},
                        "conteudo": {"type": "string"},
                        "categoria": {
                            "type": "string",
                            "enum": [
                                "Milhas e Pontos",
                                "Cartoes de Credito",
                                "Hoteis e Resorts",
                                "Promocoes",
                                "Viagens",
                            ],
                        },
                        "topico": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                        },
                        "cta_url": {"type": "string"},
                        "cta_label": {"type": "string"},
                        "slug": {"type": "string"},
                        "confianca": {"type": "number"},
                        "seo_title": {"type": "string"},
                        "meta_description": {"type": "string"},
                        "imagem_prompt": {"type": "string"},
                    },
                    "required": [
                        "titulo",
                        "resumo",
                        "conteudo",
                        "categoria",
                        "topico",
                        "tags",
                        "cta_url",
                        "cta_label",
                        "slug",
                        "confianca",
                        "seo_title",
                        "meta_description",
                        "imagem_prompt",
                    ],
                },
            }
        },
    }
    response_json = _openai_request(payload)
    content = _extract_response_text(response_json)
    parsed = json.loads(content)
    return NewsDraft(
        titulo=parsed.get("titulo") or raw_article["titulo_extraido"],
        resumo=parsed.get("resumo") or raw_article["resumo_base"] or raw_article["texto_base"][:220],
        conteudo=parsed.get("conteudo") or raw_article["texto_base"],
        categoria=parsed.get("categoria") or raw_article.get("categoria_padrao") or "Milhas e Pontos",
        topico=parsed.get("topico") or "",
        tags=parsed.get("tags") or [],
        cta_url=parsed.get("cta_url") or "",
        cta_label=parsed.get("cta_label") or "",
        slug=(parsed.get("slug") or slugify(parsed.get("titulo") or raw_article["titulo_extraido"]))[:220],
        confianca=Decimal(str(parsed.get("confianca", "0.50"))),
        seo_title=parsed.get("seo_title") or "",
        meta_description=parsed.get("meta_description") or "",
        imagem_url=raw_article.get("imagem_url") or "",
        imagem_prompt=parsed.get("imagem_prompt") or "",
        metadata={"provider": "openai_schema", "raw_response": parsed},
    )


def _rewrite_with_openai(source_name: str, raw_article: dict) -> NewsDraft:
    payload = {
        "model": DEFAULT_NEWS_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_news_system_prompt(schema_mode=False),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_news_user_prompt(source_name, raw_article),
                    }
                ],
            },
        ],
        "text": {"format": {"type": "json_object"}},
    }
    response_json = _openai_request(payload)
    content = _extract_response_text(response_json)
    parsed = json.loads(content)
    return NewsDraft(
        titulo=parsed.get("titulo") or raw_article["titulo_extraido"],
        resumo=parsed.get("resumo") or raw_article["resumo_base"] or raw_article["texto_base"][:220],
        conteudo=parsed.get("conteudo") or raw_article["texto_base"],
        categoria=parsed.get("categoria") or raw_article.get("categoria_padrao") or "Milhas e Pontos",
        topico=parsed.get("topico") or "",
        tags=parsed.get("tags") or [],
        cta_url=parsed.get("cta_url") or "",
        cta_label=parsed.get("cta_label") or "",
        slug=(parsed.get("slug") or slugify(parsed.get("titulo") or raw_article["titulo_extraido"]))[:220],
        confianca=Decimal(str(parsed.get("confianca", "0.50"))),
        seo_title=parsed.get("seo_title") or "",
        meta_description=parsed.get("meta_description") or "",
        imagem_url=raw_article.get("imagem_url") or "",
        imagem_prompt=parsed.get("imagem_prompt") or "",
        metadata={"provider": "openai", "raw_response": parsed},
    )


def _fallback_rewrite(raw_article: dict) -> NewsDraft:
    title = raw_article["titulo_extraido"] or "Noticia NC Fly"
    summary_source = raw_article.get("resumo_base") or raw_article.get("texto_base") or title
    summary = summary_source[:240].rsplit(" ", 1)[0]
    body = raw_article.get("texto_base") or summary_source
    slug = slugify(title)[:220] or hashlib.sha1(title.encode("utf-8")).hexdigest()[:20]
    confidence = Decimal("0.55") if len(body) >= 400 else Decimal("0.35")
    categoria = raw_article.get("categoria_padrao") or "Milhas e Pontos"
    return NewsDraft(
        titulo=title,
        resumo=summary,
        conteudo=body,
        categoria=categoria,
        topico="",
        tags=[],
        cta_url="",
        cta_label="",
        slug=slug,
        confianca=confidence,
        seo_title=title,
        meta_description=summary,
        imagem_url=raw_article.get("imagem_url") or "",
        imagem_prompt=_build_cover_prompt(title, summary, categoria),
        metadata={"provider": "fallback"},
    )


def build_news_draft(source_name: str, raw_article: dict) -> NewsDraft:
    try:
        draft = _rewrite_with_openai_schema(source_name, raw_article)
    except Exception:
        try:
            draft = _rewrite_with_openai(source_name, raw_article)
        except Exception:
            draft = _fallback_rewrite(raw_article)
    return _apply_quality_rules(draft, raw_article)


def _render_svg_cover_legacy(title: str, category: str) -> bytes:
    safe_title = (title[:70] + "...") if len(title) > 70 else title
    safe_category = category or "NC Fly"
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#0f172a"/>
          <stop offset="60%" stop-color="#ff6b6b"/>
          <stop offset="100%" stop-color="#f5a623"/>
        </linearGradient>
      </defs>
      <rect width="1600" height="900" fill="url(#bg)"/>
      <circle cx="1360" cy="180" r="180" fill="rgba(255,255,255,0.08)"/>
      <circle cx="220" cy="760" r="150" fill="rgba(255,255,255,0.06)"/>
      <text x="120" y="180" fill="#bfdbfe" font-family="Segoe UI, Arial, sans-serif" font-size="28" font-weight="700">{safe_category}</text>
      <text x="120" y="320" fill="#ffffff" font-family="Segoe UI, Arial, sans-serif" font-size="72" font-weight="800">{safe_title}</text>
      <text x="120" y="760" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="34">NC Fly · Imagem ilustrativa</text>
    </svg>
    """
    return textwrap.dedent(svg).encode("utf-8")


def _wrap_svg_cover_title(title: str, width: int = 24, max_lines: int = 3) -> list[str]:
    clean_title = " ".join((title or "").split())
    return textwrap.wrap(
        clean_title,
        width=width,
        max_lines=max_lines,
        placeholder="…",
        break_long_words=False,
        break_on_hyphens=False,
    ) or ["NC Fly News"]


def _flatten_cover_parts(*parts) -> list[str]:
    flattened: list[str] = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, (list, tuple, set)):
            flattened.extend(str(item) for item in part if str(item).strip())
            continue
        flattened.append(str(part))
    return flattened


def _format_cover_brand_token(token: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9&.+-]", "", token or "")
    if not cleaned:
        return ""
    normalized = _normalize_lookup(cleaned)
    canonical = _BRAND_TOKEN_CANONICAL.get(normalized)
    if canonical:
        return canonical
    if any(char.isdigit() for char in cleaned) or cleaned.isupper():
        return cleaned.upper()
    return cleaned.capitalize()


def _clean_cover_brand_label(candidate: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9&.+-]+", candidate or "")
    cleaned_tokens: list[str] = []
    for token in tokens:
        normalized = _normalize_lookup(token)
        if not normalized:
            continue
        if normalized in _BRAND_LABEL_TOKEN_STOPWORDS:
            if cleaned_tokens:
                break
            continue
        cleaned_tokens.append(_format_cover_brand_token(token))
        if len(cleaned_tokens) >= 4:
            break
    if not cleaned_tokens:
        return ""
    return " ".join(cleaned_tokens).strip()


def _find_known_cover_theme(haystack: str) -> dict[str, str] | None:
    best_theme: dict[str, str] | None = None
    best_alias_length = -1
    for theme in BRAND_COVER_THEMES:
        for alias in theme["aliases"]:
            normalized_alias = _normalize_lookup(alias)
            if normalized_alias and normalized_alias in haystack and len(normalized_alias) > best_alias_length:
                best_theme = theme
                best_alias_length = len(normalized_alias)
    return best_theme


def _infer_cover_brand_hint(label: str, category: str = "") -> str:
    normalized_label = _normalize_lookup(label)
    normalized_category = _normalize_lookup(category)
    if any(keyword in normalized_label for keyword in ("visa", "mastercard", "american express", "amex", "black", "infinite")):
        return "Cartao em destaque"
    if any(keyword in normalized_label for keyword in ("bank", "banco", "btg", "c6", "xp", "itau", "bradesco", "santander", "inter", "porto")):
        return "Banco em destaque"
    if any(keyword in normalized_label for keyword in ("air", "airlines", "aerolineas", "companhia", "tap")):
        return "Companhia em destaque"
    if "cartoes de credito" in normalized_category:
        return "Cartao em destaque"
    return "Programa em destaque"


def _build_generic_cover_theme(label: str, category: str = "") -> dict[str, str]:
    palette_index = int(hashlib.sha1((label or "ncfly").encode("utf-8")).hexdigest(), 16) % len(GENERIC_COVER_PALETTES)
    palette = GENERIC_COVER_PALETTES[palette_index]
    return {
        "label": label,
        "aliases": (),
        "hint": _infer_cover_brand_hint(label, category),
        **palette,
    }


def _extract_cover_brand_label(*parts) -> str:
    flattened_parts = _flatten_cover_parts(*parts)
    if not flattened_parts:
        return ""

    haystack_raw = " ".join(flattened_parts)
    haystack = _normalize_lookup(haystack_raw)
    if not haystack:
        return ""

    for pattern in _COMPOSITE_BRAND_LABEL_PATTERNS:
        match = pattern.search(haystack_raw)
        if not match:
            continue
        groups = [group for group in match.groups() if group]
        if not groups:
            candidate = match.group(1)
        elif len(groups) == 2:
            candidate = " ".join(groups)
        else:
            candidate = groups[0]
        cleaned = _clean_cover_brand_label(candidate)
        if cleaned:
            return cleaned

    known_theme = _find_known_cover_theme(haystack)
    if known_theme:
        label = known_theme.get("label") or ""
        if label:
            return label

    for pattern in _GENERIC_BRAND_LABEL_PATTERNS:
        match = pattern.search(haystack_raw)
        if not match:
            continue
        cleaned = _clean_cover_brand_label(match.group(1))
        if cleaned:
            return cleaned

    return ""


def _resolve_cover_brand_theme(*parts) -> dict[str, str] | None:
    haystack_parts = _flatten_cover_parts(*parts)
    haystack = _normalize_lookup(" ".join(haystack_parts))
    if not haystack:
        return None

    explicit_label = _extract_cover_brand_label(*parts)
    theme = _find_known_cover_theme(haystack)
    if theme and explicit_label:
        return {
            **theme,
            "label": explicit_label,
            "hint": _infer_cover_brand_hint(explicit_label),
        }
    if theme:
        return theme
    if explicit_label:
        return _build_generic_cover_theme(explicit_label)
    return None


def _render_svg_cover(title: str, category: str, brand_theme: dict[str, str] | None = None) -> bytes:
    wrapped_title = _wrap_svg_cover_title(title)
    line_count = len(wrapped_title)
    if line_count == 1:
        title_font_size = 84
        line_height = 96
        title_y = 320
    elif line_count == 2:
        title_font_size = 72
        line_height = 84
        title_y = 288
    else:
        title_font_size = 60
        line_height = 72
        title_y = 252

    title_tspans = "\n".join(
        f'        <tspan x="120" dy="{0 if index == 0 else line_height}">{escape(line, quote=False)}</tspan>'
        for index, line in enumerate(wrapped_title)
    )
    safe_category = escape(" ".join((category or "NC Fly").split()), quote=False)
    background_start = (brand_theme or {}).get("background_start", "#0f172a")
    background_mid = (brand_theme or {}).get("background_mid", "#ff6b6b")
    background_end = (brand_theme or {}).get("background_end", "#f5a623")
    brand_badge = ""
    if brand_theme:
        safe_brand_label = escape(str(brand_theme.get("label", "") or ""), quote=False)
        safe_brand_hint = escape(str(brand_theme.get("hint", "") or ""), quote=False)
        wordmark_color = escape(str(brand_theme.get("wordmark_color", "#ffffff")), quote=False)
        accent_color = escape(str(brand_theme.get("accent_color", "#ffffff")), quote=False)
        brand_badge = f"""
      <g>
        <rect x="1010" y="100" width="470" height="178" rx="36" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.18)" />
        <rect x="1046" y="138" width="118" height="12" rx="6" fill="{accent_color}" opacity="0.95" />
        <text x="1046" y="178" fill="#dbeafe" font-family="Segoe UI, Arial, sans-serif" font-size="22" font-weight="700">{safe_brand_hint}</text>
        <text x="1046" y="236" fill="{wordmark_color}" font-family="Segoe UI, Arial, sans-serif" font-size="52" font-weight="900">{safe_brand_label}</text>
      </g>
        """
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="{background_start}"/>
          <stop offset="60%" stop-color="{background_mid}"/>
          <stop offset="100%" stop-color="{background_end}"/>
        </linearGradient>
      </defs>
      <rect width="1600" height="900" fill="url(#bg)"/>
      <circle cx="1360" cy="180" r="180" fill="rgba(255,255,255,0.08)"/>
      <circle cx="220" cy="760" r="150" fill="rgba(255,255,255,0.06)"/>
{brand_badge}
      <text x="120" y="180" fill="#bfdbfe" font-family="Segoe UI, Arial, sans-serif" font-size="28" font-weight="700">{safe_category}</text>
      <text x="120" y="{title_y}" fill="#ffffff" font-family="Segoe UI, Arial, sans-serif" font-size="{title_font_size}" font-weight="800">
{title_tspans}
      </text>
      <text x="120" y="760" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="34">NC Fly | Imagem ilustrativa</text>
    </svg>
    """
    return textwrap.dedent(svg).encode("utf-8")


def _render_svg_cover_for_draft(draft: NewsDraft) -> bytes:
    return _render_svg_cover(
        draft.titulo,
        draft.categoria,
        brand_theme=_resolve_cover_brand_theme(
            draft.titulo,
            draft.resumo,
            draft.conteudo,
            draft.categoria,
            draft.topico,
            draft.tags,
        ),
    )


def _save_generated_file(name: str, content: bytes) -> str:
    storage_path = default_storage.save(name, ContentFile(content))
    return storage_path


def _generate_ai_cover(prompt: str, reference_image_url: str = "") -> tuple[str | None, bool]:
    try:
        if reference_image_url:
            try:
                response_json = _openai_image_edit_request(prompt, reference_image_url)
            except Exception:
                response_json = _openai_image_generation_request(prompt)
        else:
            response_json = _openai_image_generation_request(prompt)

        image_bytes = _extract_generated_image_bytes(response_json)
        if image_bytes:
            file_name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:10]}.png"
            return _save_generated_file(file_name, image_bytes), True
    except Exception:
        return None, False
    return None, False


def ensure_cover_for_news(draft: NewsDraft) -> tuple[str | None, bool]:
    has_source_image = bool(draft.imagem_url)
    force_original_cover = _env_flag("PORTAL_FORCE_AI_IMAGES")
    use_source_reference = _env_flag("PORTAL_USE_SOURCE_IMAGE_REFERENCE", "1")

    if has_source_image and not force_original_cover:
        return None, False

    if _env_flag("PORTAL_GENERATE_AI_IMAGES") and os.environ.get("OPENAI_API_KEY"):
        prompt = draft.imagem_prompt or _build_cover_prompt(draft.titulo, draft.resumo, draft.categoria)
        reference_prompt = _build_cover_reference_prompt(draft.titulo, draft.resumo, draft.categoria)
        reference_image_url = draft.imagem_url if has_source_image and force_original_cover and use_source_reference else ""
        storage_path, generated = _generate_ai_cover(reference_prompt if reference_image_url else prompt, reference_image_url=reference_image_url)
        if not storage_path and reference_image_url:
            storage_path, generated = _generate_ai_cover(prompt)
        if storage_path:
            return storage_path, generated

    if has_source_image:
        return None, False

    file_name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{draft.slug[:50]}.svg"
    return _save_generated_file(file_name, _render_svg_cover_for_draft(draft)), True


def build_hash_from_article(url_original: str, title: str, text: str) -> str:
    digest = hashlib.sha256()
    digest.update((url_original or "").encode("utf-8"))
    digest.update((title or "").encode("utf-8"))
    digest.update((text or "").encode("utf-8"))
    return digest.hexdigest()


def resolve_status_for_draft(confidence: Decimal, source_threshold: Decimal | None = None) -> str:
    threshold = source_threshold if source_threshold is not None else DEFAULT_CONFIDENCE_THRESHOLD
    return "published" if confidence >= threshold else "draft"
