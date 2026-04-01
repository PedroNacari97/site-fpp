from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import textwrap
from typing import Any
import unicodedata
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.defaultfilters import slugify
from django.utils import timezone


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_NEWS_MODEL = os.environ.get("OPENAI_NEWS_MODEL", "gpt-4.1-mini")
DEFAULT_IMAGE_MODEL = os.environ.get("OPENAI_NEWS_IMAGE_MODEL", "gpt-image-1")
DEFAULT_CONFIDENCE_THRESHOLD = Decimal(os.environ.get("PORTAL_NEWS_CONFIDENCE_THRESHOLD", "0.70"))
ENABLE_AI_IMAGES = os.environ.get("PORTAL_GENERATE_AI_IMAGES", "0").lower() in {"1", "true", "yes", "on"}

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
    imagem_url: str = ""
    imagem_ilustrativa: bool = False
    imagem_prompt: str = ""
    metadata: dict[str, Any] | None = None


def _openai_request(payload: dict) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        OPENAI_RESPONSES_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


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
    normalized = (value or "").strip().lower()
    mapping = {
        "milhas": "Milhas e Pontos",
        "milhas e pontos": "Milhas e Pontos",
        "pontos": "Milhas e Pontos",
        "fidelidade": "Milhas e Pontos",
        "cartoes": "Cartões de Crédito",
        "cartoes de credito": "Cartões de Crédito",
        "cartões": "Cartões de Crédito",
        "cartões de crédito": "Cartões de Crédito",
        "credito": "Cartões de Crédito",
        "hoteis": "Hotéis e Resorts",
        "hotéis": "Hotéis e Resorts",
        "hoteis e resorts": "Hotéis e Resorts",
        "hotéis e resorts": "Hotéis e Resorts",
        "resorts": "Hotéis e Resorts",
        "promocoes": "Promoções",
        "promoções": "Promoções",
        "promocao": "Promoções",
        "promoção": "Promoções",
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


def _build_cover_prompt(title: str, summary: str, category: str) -> str:
    return (
        f"Capa editorial ilustrativa para uma noticia de {category}. "
        f"Tema principal: {title}. "
        f"Contexto: {summary[:220]}. "
        "Estilo premium, moderno, sofisticado, jornalistico, sem texto, sem logos de terceiros, sem marcas d'agua."
    )


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
        imagem_url=draft.imagem_url,
        imagem_ilustrativa=draft.imagem_ilustrativa,
        imagem_prompt=draft.imagem_prompt or _build_cover_prompt(titulo, resumo, categoria),
        metadata=metadata,
    )


def _rewrite_with_openai_schema(source_name: str, raw_article: dict) -> NewsDraft:
    payload = {
        "model": DEFAULT_NEWS_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Voce e editor chefe senior de um portal premium de milhas, cartoes e viagens em portugues do Brasil. "
                            "Reescreva a materia como um jornalista profissional, com narrativa clara, contexto util e linguagem editorial premium. "
                            "Nao invente fatos. Se um dado nao estiver claro, omita. "
                            "Preserve com exatidao porcentagens, datas, prazos, programas, aeroportos, companhias, valores e condicoes quando estiverem na fonte. "
                            "Se houver promocao com prazo, destaque isso no resumo ou no corpo de forma natural. "
                            "Nao exponha a fonte no corpo do texto. "
                            "Classifique a noticia em uma categoria canonica do portal e em um topico editorial interno. "
                            "Se houver links externos relevantes de promocao ou acao oficial, escolha o melhor CTA e retorne esse link. "
                            "Nunca use links de redes sociais, compartilhamento ou navegacao."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": textwrap.dedent(
                            f"""
                            Fonte: {source_name}
                            URL original: {raw_article.get('url_original')}
                            Titulo base: {raw_article.get('titulo_extraido')}
                            Data atual: {timezone.localdate().isoformat()}
                            Data base: {raw_article.get('data_publicacao_original')}
                            Resumo base: {raw_article.get('resumo_base')}
                            Links externos relevantes:
                            {json.dumps(raw_article.get('outbound_links') or [], ensure_ascii=False)}
                            Categorias e topicos do portal:
                            - Milhas e Pontos: Transferencias Bonificadas; Programas de Fidelidade; Emissoes e Resgates; Clubes e Assinaturas; Salas VIP e Beneficios; Compra e Venda de Pontos
                            - Cartoes de Credito: Lancamentos e Analises; Bonus de Adesao; Salas VIP e Beneficios; Anuidade e Isencao; Aprovacao e Renda
                            - Hoteis e Resorts: Programas Hoteleiros; Hospedagem com Pontos; Resorts e Experiencias; Destinos e Guias; Promocoes de Hospedagem
                            - Promocoes: Transferencias e Bonus; Passagens Aereas; Hoteis e Resorts; Cartoes e Cashback; Ofertas Relampago
                            Texto base:
                            {raw_article.get('texto_base')}
                            """
                        ).strip(),
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
                        "text": (
                            "Voce reescreve noticias para um portal sobre milhas. "
                            "Responda em JSON com os campos: titulo, resumo, conteudo, categoria, topico, tags, cta_url, cta_label, slug, confianca, imagem_prompt. "
                            "Mantenha referencia factual, sem inventar dados. "
                            "Preserve datas, prazos, percentuais, valores, programas e condicoes exatamente quando existirem. "
                            "Slug em minusculo com hifens. Confianca vai de 0.0 a 1.0."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": textwrap.dedent(
                            f"""
                            Fonte: {source_name}
                            URL original: {raw_article.get('url_original')}
                            Titulo base: {raw_article.get('titulo_extraido')}
                            Data atual: {timezone.localdate().isoformat()}
                            Data base: {raw_article.get('data_publicacao_original')}
                            Resumo base: {raw_article.get('resumo_base')}
                            Links externos relevantes:
                            {json.dumps(raw_article.get('outbound_links') or [], ensure_ascii=False)}
                            Texto base:
                            {raw_article.get('texto_base')}
                            """
                        ).strip(),
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


def _render_svg_cover(title: str, category: str) -> bytes:
    safe_title = (title[:70] + "...") if len(title) > 70 else title
    safe_category = category or "NC Fly"
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#0f172a"/>
          <stop offset="60%" stop-color="#1d4ed8"/>
          <stop offset="100%" stop-color="#7c3aed"/>
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


def _save_generated_file(name: str, content: bytes) -> str:
    storage_path = default_storage.save(name, ContentFile(content))
    return storage_path


def _generate_ai_cover(prompt: str) -> tuple[str | None, bool]:
    try:
        response_json = _openai_request(
            {
                "model": DEFAULT_IMAGE_MODEL,
                "input": prompt,
                "tools": [{"type": "image_generation"}],
            }
        )
        for item in response_json.get("output", []) or []:
            if item.get("type") == "image_generation_call" and item.get("result"):
                image_bytes = base64.b64decode(item["result"])
                file_name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:10]}.png"
                return _save_generated_file(file_name, image_bytes), True
    except Exception:
        return None, False
    return None, False


def ensure_cover_for_news(draft: NewsDraft) -> tuple[str | None, bool]:
    if draft.imagem_url:
        return None, False
    if ENABLE_AI_IMAGES and os.environ.get("OPENAI_API_KEY"):
        prompt = draft.imagem_prompt or _build_cover_prompt(draft.titulo, draft.resumo, draft.categoria)
        storage_path, generated = _generate_ai_cover(prompt)
        if storage_path:
            return storage_path, generated
    file_name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{draft.slug[:50]}.svg"
    return _save_generated_file(file_name, _render_svg_cover(draft.titulo, draft.categoria)), True


def build_hash_from_article(url_original: str, title: str, text: str) -> str:
    digest = hashlib.sha256()
    digest.update((url_original or "").encode("utf-8"))
    digest.update((title or "").encode("utf-8"))
    digest.update((text or "").encode("utf-8"))
    return digest.hexdigest()


def resolve_status_for_draft(confidence: Decimal, source_threshold: Decimal | None = None) -> str:
    threshold = source_threshold if source_threshold is not None else DEFAULT_CONFIDENCE_THRESHOLD
    return "published" if confidence >= threshold else "draft"
