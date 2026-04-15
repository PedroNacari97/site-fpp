from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
import hashlib
import io
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

from portal.services.brand_catalog import load_brand_catalog


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
    "- imagem_prompt: OBRIGATÓRIO: descrição visual detalhada (3-5 frases) em inglês para geração de imagem via gpt-image-1. "
    "PASSO 1 — Identifique marcas/programas/destinos no título. "
    "PASSO 2 — Use a cor HEX da marca como paleta dominante (referência: <<BRAND_COLORS_TABLE>>). "
    "PASSO 3 — Se houver destino geográfico no título (cidade, país, praia), priorize uma cena desse local. "
    "PASSO 4 — Se a pauta for sobre uma marca específica (Livelo, Esfera, Smiles, LATAM Pass, Nubank, etc.), "
    "a composição DEVE destacar o LOGO oficial da marca em posição de hero (centralizado, flutuante sobre fundo limpo "
    "ou aplicado em um único objeto principal como cartão, app ou aeronave). A identidade da marca é mais importante "
    "que a cena — quando houver dúvida, prefira 'logo em destaque sobre ambiente limpo com cores da marca'. "
    "ANTI-FESTA OBRIGATÓRIO: a palavra 'promoção' NÃO significa festa. "
    "ABSOLUTAMENTE PROIBIDO em qualquer imagem: balões, chapéus de festa, confetes, presentes, bolos, "
    "fogos de artifício, multidão celebrando, sacolas de compras, ambiente de varejo ou supermercado. "
    "Promoção de passagem = oportunidade de viagem → mostre aeronave, aeroporto, destino ou app de viagem. "
    "Cenas por categoria: "
    "'Promoções' → aircraft or destination scene with brand colors, urgency through composition not party elements; "
    "'Milhas e Pontos' → loyalty app, boarding pass, or airport with brand color lighting; "
    "'Cartões de Crédito' → premium card hero shot with brand accent lighting; "
    "'Hotéis e Resorts' → luxury hotel or infinity pool with brand color tones; "
    "'Viagens' → specific geographic landmark or destination from the article title. "
    "Estilo: professional editorial photography, natural light, clean composition. "
    "REGRA DE TEXTO NA IMAGEM (CRÍTICA): a descrição visual NÃO deve pedir textos, títulos, manchetes, headlines, "
    "slogans, taglines, percentuais escritos, preços escritos, selos com palavras, nem qualquer palavra legível na cena. "
    "NUNCA peça texto em inglês (ex: 'SALE', '35% OFF', 'DEAL', 'FLY NOW') — isso é proibido. "
    "Se a pauta mencionar desconto/bônus, represente visualmente (composição, luz, cor), nunca com número ou palavra renderizada. "
    "Sempre termine o imagem_prompt com a frase exata: "
    "'No rendered text anywhere in the image; no English words; no numbers written as text; "
    "only the official brand logo may appear, and any caption, headline or price tag is strictly forbidden.' "
    "Permitido: o LOGO oficial da marca em destaque, e nome da marca discretamente gravado em objeto físico realista "
    "(livery de aeronave, face de cartão, placa de hotel). "
    "Proibido: rostos identificáveis, watermark, qualquer texto legível além do logo da marca.\n"
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


# ─── CATÁLOGO DE MARCAS ──────────────────────────────────────────────────────
# Ordem importa: keywords mais específicos primeiro para evitar match errado.
# cor_hex: usada no prompt de imagem para dar identidade visual à cena gerada.
# logo_url: PNG/JPEG/WebP válido para uso como referência visual no GPT-image edits.
#           SVGs e URLs vazias são omitidos — a API só aceita formatos raster.
#
# ⚠️ Esta lista é mantida como FALLBACK embutido. Em runtime o pipeline usa
# ``load_brand_catalog()`` (portal/services/brand_catalog.py), que mescla
# estas entradas com o CSV ``marcas_api_brandfetch_v2.csv``.
_LEGACY_BRAND_CATALOG: list[dict] = [
    # Programas de Pontos/Milhas
    {"keywords": ["latam pass", "latampass"],         "name": "LATAM Pass",          "cor_hex": "#7000ac", "logo_url": ""},
    {"keywords": ["azul fidelidade", "tudo azul"],    "name": "Azul Fidelidade",      "cor_hex": "#5061aa", "logo_url": ""},
    {"keywords": ["livelo"],                          "name": "Livelo",               "cor_hex": "#df0978", "logo_url": "https://cdn.brandfetch.io/idcBSnzgu0/w/180/h/180/theme/dark/logo.png"},
    {"keywords": ["smiles"],                          "name": "Smiles",               "cor_hex": "#eb7f02", "logo_url": "https://cdn.brandfetch.io/idGtn14sSi/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["esfera"],                          "name": "Esfera",               "cor_hex": "#2e30ad", "logo_url": "https://cdn.brandfetch.io/idw4hqM92g/w/256/h/55/theme/dark/logo.png"},
    {"keywords": ["dotz"],                            "name": "Dotz",                 "cor_hex": "#fd7e14", "logo_url": "https://cdn.brandfetch.io/idxu_hsnK3/w/240/h/125/theme/dark/logo.png"},
    {"keywords": ["premmia"],                         "name": "Premmia",              "cor_hex": "#31db4e", "logo_url": "https://cdn.brandfetch.io/id0LIQIb4i/w/820/h/323/theme/light/logo.png"},
    # Companhias Aéreas
    {"keywords": ["latam airlines", "latam"],         "name": "LATAM Airlines",       "cor_hex": "#7000ac", "logo_url": ""},
    {"keywords": ["gol airlines", "voe gol", " gol "],"name": "GOL",                 "cor_hex": "#ff7020", "logo_url": "https://cdn.brandfetch.io/id1XOAor3l/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["azul airlines", "voe azul", " azul "], "name": "Azul Airlines",   "cor_hex": "#5061aa", "logo_url": "https://cdn.brandfetch.io/idY8UKgMnI/w/389/h/389/theme/dark/icon.jpeg"},
    {"keywords": ["avianca"],                         "name": "Avianca",              "cor_hex": "#c8102e", "logo_url": "https://cdn.brandfetch.io/idgYzF_oJj/w/960/h/960/theme/dark/icon.jpeg"},
    {"keywords": ["tap air", "tap portugal", " tap "],"name": "TAP Air Portugal",     "cor_hex": "#eb2d2e", "logo_url": "https://cdn.brandfetch.io/idYGJZtC7P/w/400/h/400/theme/dark/icon.jpeg"},
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
    {"keywords": ["aerolineas"],                      "name": "Aerolíneas Argentinas","cor_hex": "#f6bb60", "logo_url": "https://cdn.brandfetch.io/idh0TdD3uK/w/200/h/200/theme/dark/icon.png"},
    # Bancos
    {"keywords": ["nubank", "nu pagamentos"],         "name": "Nubank",               "cor_hex": "#8a05be", "logo_url": "https://cdn.brandfetch.io/idXWQ2eElW/w/1079/h/1079/theme/dark/icon.png"},
    {"keywords": ["itau", "itaú"],                    "name": "Itaú",                 "cor_hex": "#FF6200", "logo_url": "https://cdn.brandfetch.io/idAciuyyPp/w/600/h/600/theme/light/logo.webp"},
    {"keywords": ["bradesco"],                        "name": "Bradesco",             "cor_hex": "#ee032c", "logo_url": "https://cdn.brandfetch.io/idJ-h_LNzX/w/820/h/683/theme/dark/logo.png"},
    {"keywords": ["santander"],                       "name": "Santander",            "cor_hex": "#ea1d25", "logo_url": "https://cdn.brandfetch.io/idex3vA3bq/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["banco do brasil", " bb "],         "name": "Banco do Brasil",      "cor_hex": "#FCFC30", "logo_url": ""},
    {"keywords": ["caixa economica", "caixa federal"],"name": "Caixa Econômica",      "cor_hex": "#F59700", "logo_url": ""},
    {"keywords": [" inter ", "banco inter"],          "name": "Inter",                "cor_hex": "#FF6E07", "logo_url": ""},
    {"keywords": ["c6 bank", "c6bank"],               "name": "C6 Bank",              "cor_hex": "#FFE45C", "logo_url": "https://cdn.brandfetch.io/id9QKeTheX/w/400/h/400/theme/dark/icon.png"},
    {"keywords": ["btg pactual", " btg "],            "name": "BTG Pactual",          "cor_hex": "#195AB4", "logo_url": "https://cdn.brandfetch.io/id2okqRkOi/w/400/h/400/theme/dark/icon.jpeg"},
    {"keywords": ["xp investimentos", " xp "],        "name": "XP Investimentos",     "cor_hex": "#ffc60a", "logo_url": ""},
    # Cartões
    {"keywords": ["american express", "amex"],        "name": "American Express",     "cor_hex": "#006fcf", "logo_url": "https://cdn.brandfetch.io/idgUmCD6wN/w/820/h/820/theme/dark/logo.png"},
    {"keywords": ["mastercard"],                      "name": "Mastercard",           "cor_hex": "#f79e1b", "logo_url": "https://cdn.brandfetch.io/idy21VLzkM/w/180/h/180/theme/dark/logo.png"},
    {"keywords": [" visa "],                          "name": "Visa",                 "cor_hex": "#1a1f71", "logo_url": ""},
    {"keywords": [" elo "],                           "name": "Elo",                  "cor_hex": "#003933", "logo_url": ""},
    # Hotéis
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


class _BrandCatalogProxy:
    """Proxy que expõe o catálogo carregado dinamicamente via CSV como lista.

    Mantém a API antiga (``for brand in BRAND_CATALOG``) funcionando e
    garante que qualquer alteração no CSV seja pegada após
    ``load_brand_catalog.cache_clear()``.
    """

    def _data(self) -> list[dict]:
        try:
            return load_brand_catalog()
        except Exception:
            return _LEGACY_BRAND_CATALOG

    def __iter__(self):
        return iter(self._data())

    def __len__(self):
        return len(self._data())

    def __getitem__(self, item):
        return self._data()[item]


BRAND_CATALOG = _BrandCatalogProxy()


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


def _detect_brands(text: str) -> list[dict]:
    """Detecta marcas presentes no texto usando o BRAND_CATALOG.
    Usa word boundary (\\b) para evitar falsos positivos (ex: "gol" em "angola").
    Retorna lista de entradas do catálogo, sem duplicatas, na ordem de detecção."""
    normalized = _normalize_lookup(text)
    detected: list[dict] = []
    seen: set[str] = set()
    for brand in BRAND_CATALOG:
        if brand["name"] in seen:
            continue
        for kw in brand["keywords"]:
            pattern = rf"\b{re.escape(_normalize_lookup(kw))}\b"
            if re.search(pattern, normalized):
                detected.append(brand)
                seen.add(brand["name"])
                break
    return detected


# Descrições semânticas de cor por HEX — ajudam o GPT-image a entender
# o tom/atmosfera da cor, não apenas o valor numérico.
_BRAND_COLOR_SEMANTICS: dict[str, str] = {
    "#df0978": "vibrant magenta-pink (energetic, bold, modern)",
    "#eb7f02": "warm amber-orange (friendly, dynamic)",
    "#2e30ad": "deep royal blue (trustworthy, corporate)",
    "#7000ac": "rich purple (premium, prestigious)",
    "#5061aa": "medium cobalt blue (reliable, professional)",
    "#fd7e14": "bright orange (lively, accessible)",
    "#31db4e": "vivid green (fresh, rewarding)",
    "#ff7020": "vibrant orange-red (energetic, bold)",
    "#c8102e": "strong red (classic, authoritative)",
    "#eb2d2e": "bright red (decisive, impactful)",
    "#c60c30": "deep crimson (luxury, prestige)",
    "#8e2157": "dark burgundy-magenta (exclusive, refined)",
    "#05164d": "navy blue (classic, dependable)",
    "#1414d2": "electric blue (modern, bold)",
    "#e51937": "vivid red (iconic, powerful)",
    "#0078d2": "sky blue (open, trustworthy)",
    "#2f5e9e": "steel blue (reliable, British)",
    "#0032a0": "cobalt blue (professional, stable)",
    "#c70a0c": "rich red (bold, international)",
    "#0095db": "bright cyan-blue (clean, Dutch)",
    "#8a05be": "deep violet (innovative, disruptive)",
    "#FF6200": "warm orange (approachable, Brazilian)",
    "#ee032c": "bright red (strong, financial)",
    "#ea1d25": "vivid red (modern banking)",
    "#FCFC30": "bright yellow (national, institutional)",
    "#F59700": "golden amber (accessible, inclusive)",
    "#FF6E07": "vibrant orange (digital, modern)",
    "#FFE45C": "soft yellow (calm, digital)",
    "#195AB4": "strong blue (institutional, financial)",
    "#ffc60a": "golden yellow (investment, growth)",
    "#006fcf": "classic blue (prestige, premium)",
    "#f79e1b": "amber-gold (global, trusted)",
    "#1a1f71": "dark navy blue (secure, global)",
    "#003933": "dark teal-green (solid, financial)",
    "#FF9962": "soft peach-coral (welcoming, luxury hospitality)",
    "#0E468B": "deep blue (elegant, established)",
    "#FFB612": "golden yellow (warm, aspirational)",
    "#1F4456": "dark teal (refined, international)",
    "#B88D5B": "warm gold (sophisticated, premium hospitality)",
    "#0071C2": "bright blue (digital, modern travel)",
    "#ff385c": "coral-red (vibrant, community)",
    "#550fed": "electric purple (bold, tech travel)",
    "#050c16": "near-black navy (serious, specialist)",
}


def _brand_color_context(brands: list[dict]) -> str:
    """Gera instrução de cor com contexto semântico para o prompt de imagem."""
    if not brands:
        return ""
    top = brands[:3]
    if len(top) == 1:
        b = top[0]
        semantic = _BRAND_COLOR_SEMANTICS.get(b["cor_hex"], "distinctive brand color")
        return (
            f"Use {b['name']}'s brand color {b['cor_hex']} ({semantic}) as the dominant "
            f"color accent — apply it as atmospheric lighting, bokeh, or environmental tones. "
            f"Keep it as accent (30-40% of composition), not a solid fill."
        )
    parts = []
    for b in top:
        semantic = _BRAND_COLOR_SEMANTICS.get(b["cor_hex"], "brand color")
        parts.append(f"{b['name']}: {b['cor_hex']} ({semantic})")
    colors = "; ".join(parts)
    return (
        f"Blend these brand color accents harmoniously in the scene: {colors}. "
        f"Use them as atmospheric lighting and environmental tones, not solid fills."
    )


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
    """Constrói prompt de imagem contextualizado por título, categoria e marcas detectadas."""
    # NOTE: dados de marca (nome, cor_hex, logo_url) vêm do model gestao.MarcaCatalogo
    # via portal.services.brand_catalog.BRAND_CATALOG — é um catálogo curado, não inferência.
    title_lower = (title + " " + summary).lower()

    detected_brands = _detect_brands(title + " " + summary)
    color_instruction = _brand_color_context(detected_brands)
    brand_focus = ""
    primary_for_fallback = None
    if detected_brands:
        primary = detected_brands[0]
        primary_for_fallback = primary
        brand_focus = (
            f"BRAND KIT (CURATED): The brand for this article is {primary['name']}. "
            f"Its official primary color is {primary.get('cor_hex', '')} — treat this hex as a "
            f"SUGGESTED reference, not a strict rule. You may use the exact hex when it fits the "
            f"scene, OR tones strongly associated with the brand identity (e.g., Livelo → vibrant "
            f"pink/magenta family; LATAM → purple family; GOL → orange/yellow family; Nubank → deep "
            f"violet family), OR a complementary palette that still reads as this brand. Goal: "
            f"perceived visual coherence with the brand, not pharmaceutical reproduction of the hex. "
            f"When an official logo is provided as a reference image, that logo IS INTOUCHABLE: "
            f"DO NOT reinterpret, redraw, recolor, translate, italicize, stylize, stretch, skew, "
            f"rotate beyond ±5°, crop, emboss or filter it. Reposition and compose around it, but the "
            f"logo pixels stay pixel-accurate with 8–12% breathing room on every side. Place the logo "
            f"as the visual protagonist (centered hero or strong focal position) OR applied cleanly "
            f"onto a single realistic object (credit card face, loyalty app screen, boarding pass, "
            f"aircraft tail, hotel sign). "
        )

    # Cena base por categoria/contexto
    if category == "Promoções" or "promoç" in title_lower or "oferta" in title_lower or "desconto" in title_lower:
        scene = (
            "Travel deal editorial scene: modern smartphone in hero position with glowing screen "
            "showing a flight deal, dynamic composition with sense of urgency and opportunity, "
            "bokeh lighting, clean and energetic layout."
        )
    elif "transferên" in title_lower or "bonificad" in title_lower or "transfer" in title_lower:
        scene = (
            "Futuristic digital dashboard showing loyalty points multiplying rapidly, "
            "holographic number display, sleek tech environment, sense of growth and gain."
        )
    elif category == "Milhas e Pontos" or "milhas" in title_lower or "pontos" in title_lower or "fidelidade" in title_lower:
        scene = (
            "Modern international airport at dawn: illuminated runway with aircraft taking off, "
            "stylized boarding pass and loyalty card in foreground on reflective surface, "
            "warm golden light, wide aspirational composition evoking freedom to travel."
        )
    elif category == "Cartões de Crédito" or "cartão" in title_lower or "cartao" in title_lower:
        scene = (
            "Premium credit card in hero position on dark marble surface, "
            "sophisticated urban financial lifestyle, soft studio lighting with gentle reflection, "
            "blurred night cityscape in background, sense of exclusivity."
        )
    elif category == "Hotéis e Resorts" or "hotel" in title_lower or "resort" in title_lower:
        scene = (
            "Infinity pool overlooking the ocean at golden hour, luxury hotel architecture, "
            "warm sunlight reflecting on water, premium travel editorial photography style."
        )
    else:
        scene = (
            "Modern commercial aircraft in flight over urban landscape at dusk, "
            "sky in deep orange and blue tones, wide aspirational aerial composition, "
            "sense of discovery and travel, photorealistic high quality."
        )

    # Fallback de marca SEM logo (temos nome + cor, mas logo_url não está disponível):
    # se a IA reconhecer a marca pelo conhecimento geral (Nubank, GOL, LATAM etc.), pode
    # renderizar o logo oficial — desde que fiel à identidade real, NUNCA inventar marca fictícia
    # nem criar variações criativas de logos conhecidos.
    no_logo_instruction = ""
    if primary_for_fallback and not primary_for_fallback.get("logo_url"):
        no_logo_instruction = (
            f"NO LOGO IMAGE PROVIDED: We do not have a logo file for {primary_for_fallback['name']} "
            f"in the catalog right now. If you genuinely know this brand's official visual identity "
            f"from general knowledge, you MAY render its real logo (correct symbol, typography and "
            f"colors) faithfully — no creative reinterpretation, no stylized variants, no \"inspired "
            f"by\" versions. If you are not confident the rendered logo will be faithful to the real "
            f"brand, fall back to typography only: write \"{primary_for_fallback['name']}\" ONCE in "
            f"clean modern sans-serif (Inter, Helvetica, Geist), spelled exactly as given, no "
            f"taglines. STRICTLY FORBIDDEN under any condition: invent fictitious brands, fabricate "
            f"a fake logo/monogram/emblem, or produce creative variations of well-known logos. "
        )

    background_instruction = ""
    if primary_for_fallback and primary_for_fallback.get("cor_hex"):
        background_instruction = (
            f"BACKGROUND (SUGGESTION): The catalog color for this brand is "
            f"{primary_for_fallback['cor_hex']}. Use it as a starting reference for the dominant "
            f"background, gradient or atmospheric lighting — but you are free to use tones associated "
            f"with the brand family (slightly darker/lighter/desaturated variants, or a complementary "
            f"palette that still reads as this brand) when it produces a more coherent scene. The "
            f"goal is perceived brand identity, not exact hex reproduction. "
        )

    return (
        f"Create a photorealistic editorial image for the article: '{title}'. "
        f"{brand_focus}"
        f"{background_instruction}"
        f"{no_logo_instruction}"
        f"{scene} "
        f"{color_instruction} "
        f"Additional context: {summary[:180]}. "
        "Absolute text rules (STRICT): NO rendered text anywhere in the image — no headlines, no "
        "captions, no slogans, no price tags, no percentages written out (no '50% OFF', no '70%'), "
        "no promotional words. NEVER render English words: no 'SALE', 'OFF', 'DEAL', 'NEW', 'FLY', "
        "'FLY NOW', 'PROMO', 'HURRY', 'LIMITED', 'BUY', 'NOW'. Any discount or urgency must be "
        "expressed through composition, lighting and color, never through written words. The ONLY "
        "text allowed is (a) the official brand name in Brazilian Portuguese as provided in the "
        "brand kit, or (b) a short news headline in Brazilian Portuguese with at most 4 words — and "
        "even those are optional. The ONLY graphic mark allowed is the official brand logo from the "
        "curated brand kit (kept pixel-accurate, never reinvented), and its natural appearance on "
        "real objects (credit card face, aircraft livery, hotel signage). No identifiable faces, no "
        "watermark, no fake invented logos, no gibberish letterforms, no decorative random letters. "
        "Professional clean composition like a premium Brazilian travel magazine cover."
    )

def _build_cover_reference_prompt(title: str, summary: str, category: str) -> str:
    # NOTE: quando uma marca for detectada e tiver logo no MarcaCatalogo (BRAND_CATALOG),
    # o logo entra como imagem de referência via /images/edits — este prompt deve tratá-lo
    # como identidade oficial intocável e usar a cor_hex como background dominante.
    detected = _detect_brands(title + " " + summary)
    brand_block = ""
    if detected:
        primary = detected[0]
        brand_name = primary.get("name", "")
        brand_color = primary.get("cor_hex", "")
        has_logo = bool(primary.get("logo_url"))
        if has_logo:
            brand_block = (
                f"BRAND KIT OFICIAL (CURADO): a imagem de referência anexada é o logo oficial de "
                f"{brand_name}. NÃO redesenhe, NÃO recolora, NÃO traduza, NÃO estilize, NÃO incline, "
                f"NÃO recorte e NÃO aplique filtros sobre o logo — trate-o como elemento INTOCÁVEL, "
                f"pixel-accurate. Permitido apenas reposicionar e dar respiro de 8–12% em todos os "
                f"lados. Cor da marca {brand_color} é uma SUGESTÃO — use o hex exato quando combinar "
                f"bem com a cena, ou tons associados à identidade da marca (variantes mais escuras, "
                f"claras, dessaturadas ou paleta complementar que ainda leia como {brand_name}). O "
                f"objetivo é coerência visual com a marca, não reprodução exata do hex. Componha "
                f"elementos abstratos (formas, gradientes, luz) ao redor do logo, mas o logo "
                f"permanece como ele é. "
            )
        else:
            brand_block = (
                f"BRAND KIT OFICIAL (CURADO, SEM IMAGEM DE LOGO): a marca é {brand_name}, cor de "
                f"referência {brand_color} (sugestão, não regra estrita — tons associados à marca "
                f"também valem). Não temos arquivo de logo no catálogo agora. Se você conhece a "
                f"identidade visual real de {brand_name} pelo conhecimento geral, PODE renderizar o "
                f"logo oficial (símbolo, tipografia e cores fiéis ao real) — sem variações criativas, "
                f"sem versões \"inspired by\". Se não tiver certeza de fidelidade, use apenas "
                f"tipografia: escreva \"{brand_name}\" UMA vez em sans-serif moderno e limpo (Inter, "
                f"Helvetica, Geist), grafia exata, sem tagline. PROIBIDO em qualquer caso: inventar "
                f"marcas fictícias, fabricar logo/símbolo/monograma falso, ou criar variações "
                f"criativas de logos conhecidos. "
            )

    return (
        f"Edite a imagem de referência para criar um post de Instagram original da marca NCfly. "
        f"Tema: {title}. Contexto: {summary[:220]}. "
        f"{brand_block}"

        "Regras obrigatórias: "
        "- NÃO manter o mesmo enquadramento da imagem original "
        "- Aplicar crop diferente ou zoom criativo "
        "- Alterar iluminação e contraste para criar nova identidade visual "
        "- Aplicar overlay escuro ou gradiente para dar destaque "
        "- Reorganizar completamente a composição visual "
        "- Quando houver logo de marca anexado, ele é INTOCÁVEL: reposicionar, sim; redesenhar, NUNCA "

        "Objetivo: "
        "A imagem final deve parecer um post de marca próprio, e NÃO uma variação da imagem original. "

        "Proibido (texto): "
        "- qualquer texto legível na imagem (headlines, legendas, preços, porcentagens, slogans) "
        "- QUALQUER palavra em inglês renderizada na imagem: SALE, OFF, DEAL, NEW, FLY, FLY NOW, "
        "  PROMO, HURRY, LIMITED, BUY, NOW, BIG, BEST "
        "- números grandes promocionais tipo '50% OFF', '70%', 'R$ 99' "
        "- letras fake/gibberish que pareçam texto "
        "- qualquer frase legível em qualquer idioma "

        "Texto permitido (opcional, no máximo um): o nome oficial da marca em português grafado em "
        "sans-serif limpa, OU o título curto da notícia em português com até 4 palavras. "

        "Proibido (composição): "
        "- manter mesma composição da imagem original "
        "- manter mesmo ângulo "
        "- parecer cópia da imagem original "
        "- inventar marca fictícia ou criar variações criativas de logos conhecidos "

        "Sem watermark. Pode aparecer: o logo oficial fornecido no brand kit (intocável), OU o logo "
        "real de uma marca conhecida renderizado fielmente a partir do conhecimento geral quando "
        "não houver arquivo no catálogo."
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


def _build_brand_colors_reference() -> str:
    """Gera tabela de cores das marcas dinamicamente a partir do BRAND_CATALOG."""
    parts = []
    for brand in BRAND_CATALOG:
        semantic = _BRAND_COLOR_SEMANTICS.get(brand["cor_hex"], "")
        sem_note = f" ({semantic})" if semantic else ""
        parts.append(f"{brand['name']}={brand['cor_hex']}{sem_note}")
    return ", ".join(parts)


def _build_news_system_prompt(*, schema_mode: bool) -> str:
    output_rule = (
        "Responda apenas com o JSON aceito pelo schema informado. Não inclua texto fora do JSON."
        if schema_mode
        else f"Responda apenas com JSON válido contendo exatamente estes campos: {NEWS_JSON_FIELDS}. Não inclua texto fora do JSON."
    )
    brand_colors = _build_brand_colors_reference()
    base = _SYSTEM_PROMPT_REWRITE.replace(
        "<<BRAND_COLORS_TABLE>>",
        brand_colors,
    )
    return f"{base}\n\n{output_rule}"


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


def _png_bytes_to_webp(png_bytes: bytes, quality: int = 85) -> bytes:
    """Converte bytes PNG para WebP usando Pillow. Fallback: retorna PNG original."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(png_bytes)) as img:
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=quality, method=6)
            return buf.getvalue()
    except Exception:
        return png_bytes


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Converte '#RRGGBB' (ou 'RRGGBB') para tupla RGB. Fallback preto."""
    value = (hex_color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (15, 23, 42)
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return (15, 23, 42)


def _render_logo_only_cover(
    brand_logo_url: str,
    brand_color_hex: str,
    size: tuple[int, int] = (1600, 900),
) -> bytes | None:
    """Gera uma capa minimalista: LOGO centralizado sobre fundo com a cor da marca.

    Retorna bytes WebP (ou None se Pillow/logo indisponíveis).

    É o fallback preferido quando o /images/edits falha OU quando a saída
    viria com texto em inglês/ruim — melhor logo sozinho do que cena ruim.
    """
    if not brand_logo_url:
        return None
    try:
        from PIL import Image, ImageOps
    except Exception:
        return None

    try:
        logo_bytes, mime_type = _download_reference_image(brand_logo_url)
    except Exception:
        return None

    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        return None

    try:
        with Image.open(io.BytesIO(logo_bytes)) as logo_raw:
            logo = logo_raw.convert("RGBA")
    except Exception:
        return None

    canvas_w, canvas_h = size
    bg_rgb = _hex_to_rgb(brand_color_hex)
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_rgb)

    # Área segura: ~55% da largura / 55% da altura — logo dominante, respiração confortável
    max_w = int(canvas_w * 0.55)
    max_h = int(canvas_h * 0.55)
    logo_fitted = ImageOps.contain(logo, (max_w, max_h))

    # Centraliza
    offset_x = (canvas_w - logo_fitted.width) // 2
    offset_y = (canvas_h - logo_fitted.height) // 2
    # Paste preservando alpha do logo
    canvas.paste(logo_fitted, (offset_x, offset_y), logo_fitted)

    buf = io.BytesIO()
    try:
        canvas.save(buf, format="WEBP", quality=90, method=6)
    except Exception:
        canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _generate_ai_cover(
    prompt: str,
    reference_image_url: str = "",
    brand_logo_url: str = "",
    brand_color_hex: str = "",
) -> tuple[str | None, bool]:
    """Gera imagem de capa via GPT-image.

    Prioridade de referência visual:
    1. brand_logo_url  → usa /images/edits com logo da marca (melhor identidade)
    2. reference_image_url → usa /images/edits com imagem da fonte
    3. nenhum          → usa /images/generations puro
    4. fallback logo-only → só o logo centralizado sobre fundo da cor da marca
       (preferido a qualquer geração ruim/com texto em inglês)
    """
    def _save(image_bytes: bytes, suffix: str = "") -> str:
        webp_bytes = _png_bytes_to_webp(image_bytes)
        ext = "webp" if len(webp_bytes) < len(image_bytes) else "png"
        data = webp_bytes if ext == "webp" else image_bytes
        slug_tag = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
        tail = f"_{suffix}" if suffix else ""
        name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{slug_tag}{tail}.{ext}"
        return _save_generated_file(name, data)

    def _save_logo_only() -> str | None:
        """Fallback determinístico: logo da marca centralizado sobre cor oficial.
        Sempre preferido a nenhuma capa / a capa genérica sem contexto de marca."""
        if not brand_logo_url:
            return None
        logo_bytes = _render_logo_only_cover(brand_logo_url, brand_color_hex)
        if not logo_bytes:
            return None
        ext = "webp"
        slug_tag = hashlib.sha1((brand_logo_url + brand_color_hex).encode("utf-8")).hexdigest()[:10]
        name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{slug_tag}_logoonly.{ext}"
        return _save_generated_file(name, logo_bytes)

    # Tentativa 1: logo da marca como referência visual
    if brand_logo_url:
        try:
            response_json = _openai_image_edit_request(prompt, brand_logo_url)
            image_bytes = _extract_generated_image_bytes(response_json)
            if image_bytes:
                return _save(image_bytes), True
        except Exception:
            pass  # Fallback para geração sem logo

    # Tentativa 2: imagem da fonte como referência
    if reference_image_url:
        try:
            response_json = _openai_image_edit_request(prompt, reference_image_url)
            image_bytes = _extract_generated_image_bytes(response_json)
            if image_bytes:
                return _save(image_bytes), True
        except Exception:
            pass  # Fallback para geração pura

    # Tentativa 3: geração pura sem referência
    try:
        response_json = _openai_image_generation_request(prompt)
        image_bytes = _extract_generated_image_bytes(response_json)
        if image_bytes:
            return _save(image_bytes), True
    except Exception:
        pass  # cai no fallback logo-only

    # Tentativa 4: fallback logo-only (melhor logo sozinho que cena ruim)
    fallback_path = _save_logo_only()
    if fallback_path:
        return fallback_path, True

    return None, False


def ensure_cover_for_news(draft: NewsDraft) -> tuple[str | None, bool]:
    has_source_image = bool(draft.imagem_url)
    force_original_cover = _env_flag("PORTAL_FORCE_AI_IMAGES")
    use_source_reference = _env_flag("PORTAL_USE_SOURCE_IMAGE_REFERENCE", "1")

    if has_source_image and not force_original_cover:
        return None, False

    if _env_flag("PORTAL_GENERATE_AI_IMAGES") and os.environ.get("OPENAI_API_KEY"):
        # 🔥 NOVA LÓGICA DE PROMPT

        llm_prompt = (draft.imagem_prompt or "").strip()
        titulo = (draft.titulo or "").lower()

        # 🔒 Guardrail anti-festa (promoção de viagem ≠ festa)
        context_guardrail = (
            "CRITICAL: This is a TRAVEL/MILES/FINANCIAL news image — NOT a party or celebration. "
            "ABSOLUTELY FORBIDDEN: balloons, party hats, confetti, gift boxes, birthday cakes, "
            "retail store settings, shopping bags, fireworks, crowd celebrations. "
            "Promotion = travel deal or financial opportunity, always shown as: "
            "aircraft, airport, destination, loyalty card, smartphone with travel app, or hotel."
        )

        # 🚫 Guardrail de texto — português only e de preferência SEM texto renderizado
        text_guardrail = (
            "TEXT RULES (STRICT, NON-NEGOTIABLE): Do NOT render any readable text inside the image. "
            "No headlines, no captions, no price tags, no written percentages, no slogans, "
            "no invented brand names, no fake letterforms, no decorative random letters. "
            "NEVER render English words anywhere in the image — explicitly forbidden: "
            "'SALE', 'OFF', 'DEAL', 'NEW', 'FLY', 'FLY NOW', 'PROMO', 'HURRY', 'LIMITED', 'BUY', 'NOW', "
            "'BIG', 'BEST', 'TRAVEL', 'GO'. "
            "Forbidden also: large promotional numbers like '50% OFF', '70%', 'R$ 99'. "
            "Forbidden any readable phrase in any language. "
            "Allowed text (OPTIONAL, at most ONE): the official brand name (exactly as in the brand "
            "kit, in Brazilian Portuguese, clean modern sans-serif) OR a short news title in "
            "Brazilian Portuguese with at most 4 words. "
            "If text accidentally appears beyond that, it must be part of a real object (boarding pass "
            "destination code, airport signage) — never a marketing message. "
            "The only graphic mark allowed is the official brand logo provided in the curated brand kit."
        )

        # 🧠 Contexto de marca — lookup automático no MarcaCatalogo via BRAND_CATALOG
        # (catálogo curado: nome oficial + cor_hex + logo PNG/JPEG — tratar como verdade absoluta)
        tags_text = " ".join(draft.tags or [])
        lookup_text = f"{draft.titulo or ''} {draft.resumo or ''} {tags_text}"
        detected_brands = _detect_brands(lookup_text)
        brand_context = _brand_color_context(detected_brands)

        # 🏷️ Logo da marca principal para referência visual
        brand_logo_url = ""
        primary_brand = next((b for b in detected_brands if b.get("logo_url")), None)
        if primary_brand:
            brand_logo_url = primary_brand["logo_url"]

        # 🎨 Estilo editorial — marca aparece com base no brand kit curado
        base_style = (
            "Editorial travel photography style, high quality, professional lighting, "
            "clean composition. The ONLY brand identity that may appear is the one provided in the "
            "curated brand kit (official logo + official color from MarcaCatalogo). "
            "Do NOT introduce any other brand, fake logo or invented mark."
        )

        # 🏷️ Instrução específica quando usaremos /images/edits com o logo da marca como input.
        # O logo vem do MarcaCatalogo — é identidade oficial, NÃO é sugestão estética.
        brand_logo_instruction = ""
        if primary_brand and brand_logo_url:
            brand_name = primary_brand.get("name", "")
            brand_color = primary_brand.get("cor_hex", "")
            brand_logo_instruction = (
                f"BRAND KIT (CURATED — LOGO IS INTOUCHABLE): The attached reference image is the "
                f"official logo of {brand_name}, sourced from our curated catalog (MarcaCatalogo). "
                f"Treat it as INTOUCHABLE visual identity: preserve original colors, proportions, "
                f"letterforms and spacing pixel-accurate. Do NOT redraw, restyle, translate, italicize, "
                f"recolor, emboss, filter, skew, rotate beyond ±5°, crop or trace it by hand. "
                f"Allowed: reposition the logo and compose abstract elements around it. Required: "
                f"keep at least 8–12% padding around the logo on every side (clear breathing room). "
                f"Place the logo as the hero element (large, centered or in a strong focal position) "
                f"OR apply it cleanly onto ONE realistic object (credit card face, loyalty app screen, "
                f"boarding pass, aircraft tail, hotel sign). "
                f"BRAND COLOR (SUGGESTION): the catalog hex is {brand_color} — use it when it fits "
                f"the scene, or use tones associated with {brand_name}'s identity (variants of the "
                f"same hue, or a complementary palette that still reads as the brand). The goal is "
                f"perceived brand coherence, not exact hex reproduction. The final image must be "
                f"instantly recognizable as {brand_name}. Do NOT add any other text, slogan, tagline "
                f"or caption — only the logo itself."
            )
        elif primary_brand:
            # Detectamos a marca no catálogo, mas sem logo_url disponível.
            # Se a IA conhece a marca pelo conhecimento geral, pode renderizar o logo real fielmente.
            # Proibido: marcas fictícias e variações criativas de logos conhecidos.
            brand_name = primary_brand.get("name", "")
            brand_color = primary_brand.get("cor_hex", "")
            brand_logo_instruction = (
                f"BRAND KIT (CURATED, NO LOGO IMAGE): brand is {brand_name}, reference color "
                f"{brand_color} (suggestion — associated tones are also valid). We do NOT have a "
                f"logo file in the catalog right now. If you genuinely know {brand_name}'s real "
                f"visual identity from general knowledge, you MAY render its official logo (correct "
                f"symbol, typography and colors) faithfully — no creative variants, no \"inspired "
                f"by\" versions. If you are not confident in faithfulness, fall back to typography "
                f"only: write \"{brand_name}\" ONCE in clean modern sans-serif (Inter, Helvetica, "
                f"Geist), exactly as spelled, with generous spacing. STRICTLY FORBIDDEN: invent "
                f"fictitious brands, fabricate fake logos/monograms/emblems, or produce creative "
                f"variations of well-known logos."
            )

        # 🚀 Monta prompt final
        if llm_prompt:
            prompt = f"{llm_prompt}. {context_guardrail} {text_guardrail} {brand_context} {brand_logo_instruction} {base_style}"
        else:
            fallback = _build_cover_prompt(
                draft.titulo,
                draft.resumo,
                draft.categoria
            )
            prompt = f"{fallback}. {context_guardrail} {text_guardrail} {brand_context} {brand_logo_instruction} {base_style}"

        # 📌 Referência de imagem da fonte (quando aplicável)
        reference_image_url = (
            draft.imagem_url
            if has_source_image and force_original_cover and use_source_reference
            else ""
        )

        if reference_image_url:
            prompt = f"{prompt}. Use a imagem de referência apenas como base visual, sem copiar."

        brand_color_hex = primary_brand.get("cor_hex", "") if primary_brand else ""

        storage_path, generated = _generate_ai_cover(
            prompt,
            reference_image_url=reference_image_url,
            brand_logo_url=brand_logo_url,
            brand_color_hex=brand_color_hex,
        )

        if not storage_path and reference_image_url:
            storage_path, generated = _generate_ai_cover(
                prompt,
                brand_logo_url=brand_logo_url,
                brand_color_hex=brand_color_hex,
            )

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
