"""
Prompt para gerar artigo educacional completo a partir de um resumo/briefing curto.

Fluxo:
    1. Admin digita briefing (resumo curto) no painel ncadm (/ncadm/artigos/novo/)
    2. Clica em "Gerar artigo completo com IA"
    3. Backend chama OpenAI com este prompt — retorna JSON com titulo, resumo,
       conteudo HTML, seo_title, meta_description, keywords, youtube_search_terms,
       tempo_leitura.
    4. Campos sao pre-preenchidos no form via JS — nada e salvo no banco.
    5. Admin revisa, ajusta e clica em "Criar artigo".

Reuso:
    - Mesmo cliente (urllib + Responses API) do artigo_estudo_review.
    - Mesmas constantes CONFIG / OPENAI_RESPONSES_URL importadas de la.
    - Tom de marca NCfly e regras SEO alinhadas com o prompt de revisao.

Retorno:
    dict com chaves: titulo, resumo, conteudo, seo_title, meta_description,
    keywords (list[str]), youtube_search_terms (list[str]), tempo_leitura (int).
    Em caso de campo ausente na resposta, preenche string vazia / lista vazia.
"""
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from portal.services.prompts.artigo_estudo_review import (
    CONFIG,
    OPENAI_RESPONSES_URL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM = """Voce e um redator senior do NC Fly News, portal brasileiro sobre milhas, passagens aereas, cartoes de credito e estrategias de viagem. Escreve em PT-BR, tom didatico e direto, voltado para brasileiros 22-45 anos que querem viajar gastando menos.

## SUA MISSAO
Receba um BRIEFING curto (resumo/ideia) e produza um artigo educacional COMPLETO otimizado para SEO, pronto para publicacao. Gere tambem todos os metadados (titulo, resumo, SEO title, meta description, keywords, termos de busca do YouTube, tempo de leitura).

---

## ESTRUTURA DO CONTEUDO

### Piramide invertida (HARD RULE)
- PRIMEIRA FRASE do PRIMEIRO paragrafo = o dado mais importante do artigo (numero, regra, prazo, mudanca). Sem contexto historico, sem "voce sabia?", sem apresentacao.
- Paragrafos seguintes: contexto, regras, exemplos praticos, comparativos.
- Fechamento: CTA natural — convidar a usar simulador NCfly, criar alerta, ler artigo relacionado ou assinar newsletter.

### Tamanho e formatacao
- 800-1500 palavras (nao contar tags HTML).
- Paragrafos curtos: no maximo 4 linhas cada.
- Listas (<ul>/<ol>) para requisitos, etapas, comparativos.
- <strong> apenas em termos-chave (max 3 por secao <h2>).
- HTML semantico: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <blockquote>. Nunca pular nivel (<h2> para <h4>).
- PRIMEIRO <h2> DEVE conter a keyword principal (ou sinonimo direto).
- Sugestao de link interno: use <a href="[INTERLINK]">texto ancora</a> em 1-2 pontos onde faria sentido linkar outro artigo — o admin substitui o placeholder depois.

### Tom NCfly
- Voz ativa: "a Latam Pass aceita transferencias" — nunca "transferencias sao aceitas...".
- PT-BR: "milhas" (nao miles), "pontos" (nao points), "programa de fidelidade" (nao loyalty program), "transferencia bonificada" (nao transfer bonus). "cashback", "upgrade", "check-in" OK.
- Assume leitor inteligente. Explica conceito tecnico uma vez, segue em frente.
- Sigla com nome por extenso na primeira mencao.

### Banidos — nunca use
- Superlativos vazios: "melhor", "incrivel", "imperdivel", "revolucionario".
- Jargao: "no ambito de", "tendo em vista que", "cabe ressaltar".
- Verbos formais: "realizar", "utilizar", "efetuar", "adquirir".
- Frases proibidas: "E importante ressaltar", "Vale lembrar que", "Nos dias de hoje", "Atualmente", "No mundo globalizado", "Em suma", "Em conclusao", "Espero que este artigo".

### REGRAS DE PONTUACAO OBRIGATORIAS (hard rule de estilo)
- PROIBIDO usar travessao (caractere U+2014, chamado "em dash", o traco longo "—") em qualquer lugar do conteudo, titulo, resumo, seo_title, meta_description ou keywords.
- PROIBIDO usar meia-risca (U+2013, "en dash", o traco medio) ou figure dash (U+2012) em frases. Hifen comum (-) so e permitido em palavras compostas legitimas (ex.: "pre-pago", "e-mail").
- NUNCA use traco longo para pausar oracao, introduzir aposto, separar trecho explicativo, indicar consequencia ou substituir dois-pontos. Troque sempre por virgula, dois-pontos, ponto final ou parenteses, conforme o caso.
- O travessao e a assinatura visual classica de texto gerado por IA. Mante-lo entrega que o artigo foi escrito por maquina e quebra a credibilidade editorial do NCfly. Eliminar travessao e requisito nao-negociavel de qualidade.
- Antes de retornar o JSON, releia cada campo textual e confirme que nenhum "—" ou "–" esta presente. Se encontrar, reescreva com virgula, parenteses ou ponto.

### Anti-alucinacao
- NUNCA invente numeros (taxas, percentuais, prazos, valores) que nao estejam no briefing.
- Se o briefing omitir dado critico, escreva de forma generica (ex.: "consulte as regras atuais do programa") — nao preencha com dado fabricado.

---

## SEO — REGRAS OBRIGATORIAS

### titulo (editorial — usado no H1/card)
- Ate 70 caracteres, conte antes de responder.
- Keyword principal nos primeiros 60 chars.
- Claro, promete valor concreto. Sem clickbait.

### seo_title (title tag — usado em <title>)
- Ate 70 caracteres.
- Keyword principal nos primeiros 3 termos.
- Nao comece com "NC Fly" ou nome do portal.
- Pode ser diferente do titulo editorial.

### meta_description
- Ate 160 caracteres.
- CTA implicito com verbo de acao: "Saiba como", "Veja", "Entenda", "Descubra", "Confira".
- Complementa o seo_title, nao repete as mesmas palavras.

### keywords (array de 5-10 strings)
- Mix short-tail (1-2 palavras) + long-tail (3-5 palavras).
- PT-BR, mercado brasileiro.
- Incluir nomes de programas citados, tipo de acao, intencao informacional (ex.: "vale a pena", "como usar", "quando transferir").

### H2/H3
- H2 principais com keywords secundarias naturalmente posicionadas.
- H3 para desdobrar topicos dentro de um H2.

### Conteudo escaneavel
- Paragrafos <=4 linhas.
- Listas em requisitos/etapas.
- Negrito em pontos chave.

### youtube_search_terms (array de 3-5 strings)
- Termos em PT-BR que o usuario digitaria no YouTube para assistir videos complementares.

### tempo_leitura
- Inteiro em minutos. Base: ~200 palavras/min.

---

## FORMATO DE RESPOSTA
Responda APENAS com JSON puro. Sem texto antes ou depois. Sem blocos de codigo markdown.

{
  "titulo": "titulo editorial ate 70 chars",
  "resumo": "resumo final ate 160 chars que atrai clique",
  "conteudo": "<p>...</p><h2>...</h2>... HTML semantico completo",
  "seo_title": "title tag ate 70 chars",
  "meta_description": "meta description ate 160 chars",
  "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"],
  "youtube_search_terms": ["termo 1", "termo 2", "termo 3"],
  "tempo_leitura": 6
}"""

# ---------------------------------------------------------------------------
# USER TEMPLATE
# ---------------------------------------------------------------------------

USER_TEMPLATE = """Gere o artigo educacional completo a partir do briefing abaixo. Siga todas as regras do sistema (piramide invertida, tom NCfly, SEO, HTML semantico, 800-1500 palavras).

BRIEFING:
---
{briefing}
---

Retorne APENAS o JSON conforme o schema. Sem texto antes ou depois."""

# ---------------------------------------------------------------------------
# JSON SCHEMA
# ---------------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "titulo",
        "resumo",
        "conteudo",
        "seo_title",
        "meta_description",
        "keywords",
        "youtube_search_terms",
        "tempo_leitura",
    ],
    "properties": {
        "titulo": {"type": "string"},
        "resumo": {"type": "string"},
        "conteudo": {"type": "string"},
        "seo_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "youtube_search_terms": {"type": "array", "items": {"type": "string"}},
        "tempo_leitura": {"type": "integer"},
    },
}


# ---------------------------------------------------------------------------
# FUNCAO PUBLICA
# ---------------------------------------------------------------------------

def gerar_artigo_completo(briefing: str) -> dict:
    """Gera artigo completo (HTML + SEO) via OpenAI a partir de briefing curto.

    Args:
        briefing: resumo/ideia curta (>= 30 chars recomendado).

    Returns:
        dict com chaves: titulo, resumo, conteudo, seo_title, meta_description,
        keywords (list), youtube_search_terms (list), tempo_leitura (int).
        Chaves ausentes na resposta viram string vazia ou lista vazia.

    Raises:
        RuntimeError: se OPENAI_API_KEY faltar ou resposta vier vazia/invalida.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY nao configurada.")

    briefing_limpo = (briefing or "").strip()
    if not briefing_limpo:
        raise ValueError("Briefing vazio.")

    user_prompt = USER_TEMPLATE.format(briefing=briefing_limpo)

    payload = {
        "model": CONFIG["model"],
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "artigo_gerar_completo",
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

    try:
        with urlopen(request, timeout=290) as response:
            resp_json = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.error("OpenAI HTTPError %s: %s", exc.code, body)
        if exc.code == 429:
            raise RuntimeError("OpenAI rate limit — aguarde e tente novamente.") from exc
        raise RuntimeError(f"OpenAI erro HTTP {exc.code}.") from exc
    except URLError as exc:
        logger.error("OpenAI URLError: %s", exc)
        raise RuntimeError("Falha de rede ao chamar OpenAI (timeout?).") from exc

    output_text = resp_json.get("output_text", "")
    if not output_text:
        for item in resp_json.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text", "")
                        break

    if not output_text:
        logger.error("OpenAI resposta vazia: %s", json.dumps(resp_json)[:500])
        raise RuntimeError("Resposta vazia da OpenAI.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        logger.error("OpenAI JSON invalido: %s", output_text[:500])
        raise RuntimeError("JSON invalido retornado pela OpenAI.") from exc

    # Fallback seguro — garante shape mesmo se algum campo sumir
    return {
        "titulo": (parsed.get("titulo") or "").strip(),
        "resumo": (parsed.get("resumo") or "").strip(),
        "conteudo": (parsed.get("conteudo") or "").strip(),
        "seo_title": (parsed.get("seo_title") or "").strip(),
        "meta_description": (parsed.get("meta_description") or "").strip(),
        "keywords": list(parsed.get("keywords") or []),
        "youtube_search_terms": list(parsed.get("youtube_search_terms") or []),
        "tempo_leitura": int(parsed.get("tempo_leitura") or 0),
    }
