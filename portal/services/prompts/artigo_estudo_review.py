"""
Prompt para revisao editorial + SEO de artigos educacionais via OpenAI.

Fluxo:
    1. Usuario escreve/cola o artigo no painel ncadm
    2. Clica em "Revisao IA" — Django envia para OpenAI
    3. IA retorna JSON com conteudo revisado, SEO otimizado e notas
    4. Resultado e salvo em ArtigoEstudo.ia_revisao_json

Uso:
    from portal.services.prompts.artigo_estudo_review import SYSTEM, USER_TEMPLATE, CONFIG, SCHEMA
"""
import json
import logging
import os
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

CONFIG = {
    "model": os.environ.get("OPENAI_NEWS_MODEL", "gpt-4.1"),
    "max_tokens": 8192,
    "temperature": 0.2,
}

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM = """Voce e o editor-chefe e especialista em SEO do NC Fly, portal brasileiro sobre milhas aereas, programas de fidelidade, cartoes de credito e viagens.

## SUA MISSAO
Receba um artigo educacional (titulo + conteudo HTML) e faca uma revisao completa:
1. **Reescreva e melhore o conteudo** — clareza, didatica, estrutura, tom profissional
2. **Otimize para SEO** — titulo, meta description, keywords, headings, densidade de palavras-chave
3. **Gere todos os campos SEO** prontos para publicacao
4. **Retorne o HTML final** limpo e pronto para uso

---

## CRITERIOS DE REVISAO

### Conteudo
- Tom informativo, direto, sem jargao corporativo
- Voz ativa. Paragrafos curtos (3-5 frases)
- Conceitos tecnicos explicados na primeira mencao
- Progressao logica: conceito -> explicacao -> exemplo pratico -> conclusao
- Minimo 800 palavras no conteudo revisado
- Negrito com parcimonia (maximo 3 por secao)
- Sem superlativos vazios ("o melhor", "incrivel")
- Nao inventar dados — se algo parecer impreciso, sinalize nas notas

### Estrutura HTML
- Use <h2> para secoes principais, <h3> para subsecoes
- Use <p>, <strong>, <ul>/<ol>, <li>, <blockquote> quando apropriado
- Primeiro <h2> deve conter a keyword principal
- CTA sutil na ultima frase

### SEO
- seo_title: 55-65 caracteres, keyword principal no inicio
- meta_description: 145-155 caracteres, chamada para acao implicita
- keywords: 5-8 termos relevantes de cauda longa
- youtube_search_terms: 3-5 termos para buscar videos relacionados no YouTube
- resumo: 2-3 frases para exibicao em cards (max 280 chars)
- Densidade de keyword: 2-4 mencoes naturais no corpo

---

## FORMATO DE RESPOSTA
Responda APENAS com JSON puro. Sem texto antes ou depois. Sem blocos de codigo markdown.

{
  "titulo_revisado": "titulo otimizado para SEO",
  "resumo": "resumo curto para cards e listagens (max 280 chars)",
  "conteudo_revisado": "HTML completo revisado e otimizado",
  "seo_title": "titulo SEO 55-65 chars com keyword principal",
  "meta_description": "meta description 145-155 chars",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "youtube_search_terms": ["termo busca 1", "termo busca 2", "termo busca 3"],
  "tempo_leitura": 7,
  "resumo_revisao": "resumo em 1-2 frases do que foi alterado e por que",
  "notas_revisao": [
    {
      "tipo": "factual|clareza|estrutura|estilo|seo",
      "severidade": "alta|media|baixa",
      "descricao": "descricao do problema",
      "sugestao": "como foi corrigido"
    }
  ],
  "confianca": 0.85,
  "aprovado_para_publicacao": true
}"""

# ---------------------------------------------------------------------------
# USER TEMPLATE
# ---------------------------------------------------------------------------

USER_TEMPLATE = """Revise e otimize o artigo educacional abaixo. Melhore conteudo, estrutura, SEO e gere todos os campos necessarios.

TITULO ORIGINAL:
---
{titulo_original}
---

CONTEUDO ORIGINAL:
---
{conteudo_original}
---

Retorne o JSON completo conforme as instrucoes do sistema. JSON puro, sem texto adicional."""

# ---------------------------------------------------------------------------
# JSON SCHEMA (para OpenAI structured output)
# ---------------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "titulo_revisado",
        "resumo",
        "conteudo_revisado",
        "seo_title",
        "meta_description",
        "keywords",
        "youtube_search_terms",
        "tempo_leitura",
        "resumo_revisao",
        "notas_revisao",
        "confianca",
        "aprovado_para_publicacao",
    ],
    "properties": {
        "titulo_revisado": {"type": "string"},
        "resumo": {"type": "string"},
        "conteudo_revisado": {"type": "string"},
        "seo_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "youtube_search_terms": {"type": "array", "items": {"type": "string"}},
        "tempo_leitura": {"type": "integer"},
        "resumo_revisao": {"type": "string"},
        "notas_revisao": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tipo", "severidade", "descricao", "sugestao"],
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["factual", "clareza", "estrutura", "estilo", "seo"],
                    },
                    "severidade": {
                        "type": "string",
                        "enum": ["alta", "media", "baixa"],
                    },
                    "descricao": {"type": "string"},
                    "sugestao": {"type": "string"},
                },
            },
        },
        "confianca": {"type": "number"},
        "aprovado_para_publicacao": {"type": "boolean"},
    },
}


# ---------------------------------------------------------------------------
# FUNCAO DE CHAMADA — OpenAI Responses API
# ---------------------------------------------------------------------------

def review_artigo(titulo: str, conteudo: str) -> dict:
    """Envia artigo para revisao via OpenAI e retorna o JSON de resultado."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")

    user_prompt = USER_TEMPLATE.format(
        titulo_original=titulo,
        conteudo_original=conteudo,
    )

    payload = {
        "model": CONFIG["model"],
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "artigo_estudo_review",
                "strict": True,
                "schema": SCHEMA,
            }
        },
        "temperature": CONFIG["temperature"],
        "max_output_tokens": CONFIG["max_tokens"],
    }

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

    with urlopen(request, timeout=120) as response:
        resp_json = json.loads(response.read().decode("utf-8"))

    # Extrair texto da resposta
    output_text = resp_json.get("output_text", "")
    if not output_text:
        for item in resp_json.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content["text"]
                        break

    if not output_text:
        raise RuntimeError(f"Resposta vazia da OpenAI: {json.dumps(resp_json)[:500]}")

    return json.loads(output_text)
