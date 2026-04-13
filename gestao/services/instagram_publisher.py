"""
Agente: Arquitetura Sênior — NCfly
Módulo: instagram_publisher

Pipeline de publicação automática no Instagram via Meta Graph API.
Desacoplado do core de notícias — acionado via callback on_published.

Fluxo:
  1. Gerar prompt de imagem (OpenAI)
  2. Gerar imagem 1:1 original (OpenAI gpt-image-1.5)
  3. Salvar imagem no storage do Django (S3 ou local)
  4. Gerar legenda adaptada para Instagram (OpenAI)
  5. Criar container de mídia (POST /media)
  6. Aguardar container ficar pronto (polling status_code)
  7. Publicar container (POST /media_publish)
  8. Registrar resultado em InstagramNoticiaEvento

Variáveis de ambiente obrigatórias (Railway):
  INSTAGRAM_IG_USER_ID   — ID do usuário do Instagram Business
  INSTAGRAM_ACCESS_TOKEN — Token de acesso da Meta Graph API

Variáveis opcionais:
  INSTAGRAM_AUTO_PUBLISH    — "0" desabilita (padrão: "1")
  INSTAGRAM_PUBLISH_RETRIES — tentativas por etapa (padrão: 3)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v22.0"
_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
_OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"

# Fallback caption quando a geração via IA falha
_FALLBACK_CAPTION_TEMPLATE = (
    "{resumo:.200}\n\nTodos os detalhes no link da bio. ✈️"
    "\n\n#milhas #viagens #aviacao #ncfly #passagens #milhasaereas"
)


# ─── CONFIGURAÇÃO ────────────────────────────────────────────────────────────


def get_instagram_config() -> dict:
    return {
        "ig_user_id": getattr(settings, "INSTAGRAM_IG_USER_ID", "").strip(),
        "access_token": getattr(settings, "INSTAGRAM_ACCESS_TOKEN", "").strip(),
        "auto_publish": getattr(settings, "INSTAGRAM_AUTO_PUBLISH", True),
        "retries": int(getattr(settings, "INSTAGRAM_PUBLISH_RETRIES", 3)),
    }


def is_instagram_configured() -> bool:
    config = get_instagram_config()
    return bool(config["ig_user_id"] and config["access_token"])


# ─── UTILITÁRIOS OPENAI ──────────────────────────────────────────────────────


def _get_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    return key


def _openai_post(url: str, payload: dict, timeout: int = 90) -> dict:
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
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_openai_text(response: dict) -> str:
    if response.get("output_text"):
        return response["output_text"].strip()
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"].strip()
    return ""


def _extract_image_bytes(response: dict) -> bytes | None:
    data = (response.get("data") or [])
    if not data:
        return None
    first = data[0] or {}
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"])
    if first.get("url"):
        req = Request(first["url"])
        with urlopen(req, timeout=60) as resp:
            return resp.read()
    return None


# ─── GERAÇÃO DE IMAGEM ───────────────────────────────────────────────────────


def _build_instagram_image_prompt(noticia) -> str:
    """Usa OpenAI para construir um prompt de imagem original para Instagram."""
    from portal.services.instagram_prompts import (
        IMAGE_SYSTEM,
        IMAGE_USER_TEMPLATE,
        CONFIG,
    )

    imagem_prompt_original = (noticia.metadata_json or {}).get("imagem_prompt", "")
    user_message = IMAGE_USER_TEMPLATE.format(
        titulo=noticia.titulo,
        categoria=noticia.categoria or "Milhas e Pontos",
        resumo=noticia.resumo,
        imagem_prompt=imagem_prompt_original,
    )

    try:
        response = _openai_post(
            _OPENAI_RESPONSES_URL,
            {
                "model": CONFIG["model"],
                "instructions": IMAGE_SYSTEM,
                "input": user_message,
                "max_output_tokens": CONFIG["max_tokens"],
                "temperature": CONFIG["temperature"],
            },
        )
        prompt = _extract_openai_text(response)
        if prompt:
            return prompt
    except Exception as exc:
        logger.warning("Instagram: falha ao gerar prompt de imagem via IA: %s", exc)

    # Fallback: usa o prompt original da notícia ou um genérico
    return (
        imagem_prompt_original
        or f"Photorealistic travel scene with airplanes, airport lounge, and luxury travel vibes. "
           f"Clean composition, square format, no text, no watermarks. Theme: {noticia.categoria or 'travel and miles'}."
    )


def _generate_and_store_instagram_image(image_prompt: str) -> tuple[str | None, str | None]:
    """
    Gera imagem 1:1 via OpenAI e salva no storage.
    Retorna (storage_path, public_url) ou (None, None) em falha.
    """
    from portal.services.instagram_prompts import CONFIG

    payload = {
        "model": CONFIG["image_model"],
        "prompt": image_prompt,
        "size": CONFIG["image_size"],
        "quality": CONFIG["image_quality"],
    }

    response = _openai_post(_OPENAI_IMAGES_URL, payload, timeout=120)
    image_bytes = _extract_image_bytes(response)
    if not image_bytes:
        raise ValueError("OpenAI não retornou bytes de imagem.")

    prompt_hash = hashlib.sha1(image_prompt.encode("utf-8")).hexdigest()[:10]
    file_name = f"portal/instagram/generated/{timezone.now():%Y%m%d%H%M%S}_{prompt_hash}.png"
    storage_path = default_storage.save(file_name, ContentFile(image_bytes))
    public_url = _get_public_image_url(storage_path)
    return storage_path, public_url


def _get_public_image_url(storage_path: str) -> str:
    """Retorna a URL pública de um arquivo salvo no storage do Django."""
    url = default_storage.url(storage_path)
    if url.startswith("http"):
        return url
    # Storage local: prefixar com SITE_BASE_URL para que a Meta consiga acessar
    site_base_url = getattr(settings, "SITE_BASE_URL", "").strip().rstrip("/")
    if site_base_url:
        return f"{site_base_url}{url}"
    return url


def _resolve_instagram_image(noticia, retries: int = 3) -> tuple[str | None, str | None]:
    """
    Resolve a imagem para publicação no Instagram.

    Ordem de prioridade:
    1. Imagem já salva no storage do site (PNG/JPG gerada por IA) — proporção 1536x1024
       que é 1.5:1, dentro do limite aceito pelo Instagram (máx 1.91:1). Sem corte.
    2. imagem_url da notícia (se existir e não for SVG).
    3. Geração de nova imagem via OpenAI (fallback quando não há imagem no storage).

    Retorna (storage_path_or_None, public_url).
    """
    # 1. Imagem salva no storage — prioridade máxima (original, sem corte no Instagram)
    if noticia.imagem and noticia.imagem.name:
        image_name = noticia.imagem.name
        if not image_name.lower().endswith(".svg"):
            public_url = _get_public_image_url(image_name)
            logger.info("Instagram: usando imagem do site: %s", public_url)
            return None, public_url
        logger.debug("Instagram: imagem do site é SVG, não suportado pela Meta. Buscando alternativa.")

    # 2. imagem_url externa (apenas se não for de terceiro — respeita imagem_ilustrativa)
    if noticia.imagem_url and noticia.imagem_ilustrativa:
        logger.info("Instagram: usando imagem_url ilustrativa: %s", noticia.imagem_url)
        return None, noticia.imagem_url

    # 3. Fallback: gera nova imagem via OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        logger.info("Instagram: nenhuma imagem no storage — gerando via IA.")
        image_prompt = _build_instagram_image_prompt(noticia)
        try:
            return _with_retry(
                lambda: _generate_and_store_instagram_image(image_prompt),
                retries=retries,
            )
        except Exception as exc:
            logger.warning(
                "Instagram: geração de imagem via IA falhou após %d tentativas: %s.",
                retries,
                exc,
            )

    raise ValueError(
        "Sem imagem disponível para Instagram. "
        "A notícia precisa ter uma imagem salva no storage ou OPENAI_API_KEY configurada."
    )


# ─── GERAÇÃO DE LEGENDA ──────────────────────────────────────────────────────


def _generate_instagram_caption(noticia) -> str:
    """Usa OpenAI para gerar legenda adaptada ao Instagram."""
    from portal.services.instagram_prompts import (
        CAPTION_SYSTEM,
        CAPTION_USER_TEMPLATE,
        CONFIG,
    )

    site_base_url = getattr(settings, "SITE_BASE_URL", "https://ncfly.com.br").strip().rstrip("/")
    try:
        noticia_url = f"{site_base_url}{noticia.get_absolute_url()}"
    except Exception:
        noticia_url = site_base_url

    tags_str = ", ".join(noticia.tags_json or [])
    user_message = CAPTION_USER_TEMPLATE.format(
        titulo=noticia.titulo,
        resumo=noticia.resumo,
        categoria=noticia.categoria or "Milhas e Pontos",
        tags=tags_str,
        url_noticia=noticia_url,
    )

    try:
        response = _openai_post(
            _OPENAI_RESPONSES_URL,
            {
                "model": CONFIG["model"],
                "instructions": CAPTION_SYSTEM,
                "input": user_message,
                "max_output_tokens": CONFIG["max_tokens"],
                "temperature": CONFIG["temperature"],
            },
        )
        caption = _extract_openai_text(response)
        if caption:
            return caption
    except Exception as exc:
        logger.warning("Instagram: falha ao gerar legenda via IA: %s", exc)

    # Fallback: legenda mínima com resumo
    return _FALLBACK_CAPTION_TEMPLATE.format(resumo=noticia.resumo)


# ─── META GRAPH API ──────────────────────────────────────────────────────────


def _graph_post(path: str, access_token: str, data: dict, timeout: int = 60) -> dict:
    """POST genérico para a Meta Graph API."""
    url = f"{_GRAPH_API_BASE}/{path}"
    payload = {**data, "access_token": access_token}
    encoded = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta API HTTP {exc.code}: {body}") from exc
    if "error" in result:
        raise RuntimeError(f"Meta API error: {result['error']}")
    return result


def _create_media_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    """
    Cria container de mídia no Instagram.
    Retorna o container ID.
    """
    result = _graph_post(
        f"{ig_user_id}/media",
        access_token,
        {"image_url": image_url, "caption": caption},
    )
    container_id = result.get("id")
    if not container_id:
        raise ValueError(f"Meta API não retornou container ID. Resposta: {result}")
    return container_id


def _wait_for_container_ready(ig_user_id: str, access_token: str, container_id: str, max_wait: int = 90) -> None:
    """
    Polling do status do container até FINISHED.
    Lança TimeoutError se não ficar pronto dentro de max_wait segundos.
    """
    url = f"{_GRAPH_API_BASE}/{container_id}?fields=status_code&access_token={access_token}"
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {container_id} em estado {status}.")
            logger.debug("Instagram: container %s status=%s, aguardando...", container_id, status)
        except (RuntimeError, ValueError):
            raise
        except Exception as exc:
            logger.warning("Instagram: erro ao consultar status do container: %s", exc)
        time.sleep(5)
    raise TimeoutError(f"Container {container_id} não ficou pronto em {max_wait}s.")


def _publish_media_container(ig_user_id: str, access_token: str, container_id: str) -> str:
    """
    Publica o container de mídia.
    Retorna o post ID.
    """
    result = _graph_post(
        f"{ig_user_id}/media_publish",
        access_token,
        {"creation_id": container_id},
    )
    post_id = result.get("id")
    if not post_id:
        raise ValueError(f"Meta API não retornou post ID. Resposta: {result}")
    return post_id


# ─── RETRY ───────────────────────────────────────────────────────────────────


def _with_retry(fn, retries: int = 3, wait_seconds: int = 5):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Instagram: tentativa %d/%d falhou: %s",
                attempt + 1,
                retries,
                exc,
            )
            if attempt < retries - 1:
                time.sleep(wait_seconds)
    raise last_exc  # type: ignore[misc]


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────


def publish_noticia_to_instagram(noticia) -> None:
    """
    Ponto de entrada do pipeline de publicação no Instagram.
    Chamado como callback on_published pelo news_sync_service.

    Fire-and-forget: nunca levanta exceção — todos os erros são
    registrados em InstagramNoticiaEvento e logados.
    """
    from gestao.models.instagram_noticia_evento import InstagramNoticiaEvento

    if not is_instagram_configured():
        logger.debug(
            "Instagram: INSTAGRAM_IG_USER_ID ou INSTAGRAM_ACCESS_TOKEN não configurados. "
            "Publicação ignorada para notícia %s.",
            getattr(noticia, "pk", "?"),
        )
        return

    config = get_instagram_config()

    if not config.get("auto_publish", True):
        logger.debug(
            "Instagram: INSTAGRAM_AUTO_PUBLISH=0. Publicação ignorada para notícia %s.",
            noticia.pk,
        )
        return

    # Idempotência: não publicar a mesma notícia duas vezes
    if InstagramNoticiaEvento.objects.filter(
        noticia=noticia,
        status=InstagramNoticiaEvento.STATUS_PUBLICADO,
    ).exists():
        logger.debug(
            "Instagram: notícia %s já publicada com sucesso anteriormente. Ignorando.",
            noticia.pk,
        )
        return

    evento = InstagramNoticiaEvento.objects.create(
        noticia=noticia,
        status=InstagramNoticiaEvento.STATUS_PENDENTE,
    )

    try:
        retries = config["retries"]
        ig_user_id = config["ig_user_id"]
        access_token = config["access_token"]

        # Etapa 1: imagem original para Instagram
        logger.info("Instagram [%s]: gerando imagem para notícia %s", ig_user_id, noticia.pk)
        _, image_url = _resolve_instagram_image(noticia, retries=retries)

        if not image_url:
            raise ValueError("URL da imagem vazia após resolução.")

        # Etapa 2: legenda adaptada ao Instagram
        logger.info("Instagram [%s]: gerando legenda para notícia %s", ig_user_id, noticia.pk)
        caption = _generate_instagram_caption(noticia)

        # Etapa 3: criar container de mídia
        logger.info("Instagram [%s]: criando container de mídia", ig_user_id)
        container_id = _with_retry(
            lambda: _create_media_container(ig_user_id, access_token, image_url, caption),
            retries=retries,
        )

        # Etapa 4: aguardar processamento do container pela Meta
        logger.info("Instagram [%s]: aguardando container %s ficar pronto", ig_user_id, container_id)
        _wait_for_container_ready(ig_user_id, access_token, container_id)

        # Etapa 5: publicar
        logger.info("Instagram [%s]: publicando container %s", ig_user_id, container_id)
        post_id = _with_retry(
            lambda: _publish_media_container(ig_user_id, access_token, container_id),
            retries=retries,
        )

        # Etapa 6: registrar sucesso
        evento.status = InstagramNoticiaEvento.STATUS_PUBLICADO
        evento.ig_media_id = container_id
        evento.ig_post_id = post_id
        evento.caption = caption
        evento.image_url = image_url
        evento.tentativas = 1
        evento.publicado_em = timezone.now()
        evento.payload_json = {
            "container_id": container_id,
            "post_id": post_id,
            "image_url": image_url,
        }
        evento.save()

        logger.info(
            "Instagram: notícia %s publicada com sucesso. Post ID: %s",
            noticia.pk,
            post_id,
        )

    except Exception as exc:
        logger.error(
            "Instagram: erro ao publicar notícia %s: %s",
            getattr(noticia, "pk", "?"),
            exc,
            exc_info=True,
        )
        evento.status = InstagramNoticiaEvento.STATUS_ERRO
        evento.erro = str(exc)[:2000]
        evento.tentativas = (evento.tentativas or 0) + 1
        evento.save(update_fields=["status", "erro", "tentativas"])
