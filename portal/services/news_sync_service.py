from __future__ import annotations

import hashlib
import re
import traceback
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.db import transaction
from django.template.defaultfilters import slugify
from django.utils import timezone

from portal.models import Fonte, JobExecucao, MateriaBruta, NoticiaPublicada
from portal.services.ai_pipeline import (
    NewsDraft,
    _apply_quality_rules,
    _extract_cover_brand_label,
    _render_svg_cover_for_draft,
    _save_generated_file,
    build_hash_from_article,
    build_news_draft,
    ensure_cover_for_news,
    resolve_status_for_draft,
)
from portal.services.deduplication import (
    append_source_reference,
    build_story_fingerprint,
    find_duplicate_news,
)
from portal.services.fetchers.base import FetchedEntry
from portal.services.fetchers.registry import get_fetcher_for_source


def sync_news_progressive(limit: int = 10, on_published=None):
    """
    Sincroniza noticias publicando uma a uma.
    Chama on_published(noticia) para cada noticia publicada.
    Retorna (processadas, publicadas, erros).
    """
    _ensure_default_sources()
    job = JobExecucao.objects.create(job_name="sync_home_news", status="running", horario=timezone.now())
    processed = 0
    published = 0
    errors = []

    # URLs que ja tem noticia publicada, filtrar antes de processar.
    already_published_urls = set(
        MateriaBruta.objects.filter(
            noticia_publicada__status="published"
        ).values_list("url_original", flat=True)
    )

    queryset = Fonte.objects.filter(ativa=True)
    try:
        for source in queryset:
            fetcher = get_fetcher_for_source(source)
            try:
                # Busca candidatos e filtra URLs ja publicadas antes de fatiar pelo limit.
                cutoff = timezone.now() - timedelta(days=3)
                all_entries = fetcher.list_entries(source)
                fresh_entries = [
                    e for e in all_entries
                    if e.url not in already_published_urls
                    and (e.published_at is None or e.published_at >= cutoff)
                ]
                entries = fresh_entries[:limit]
            except Exception as exc:
                errors.append(f"[{source.nome}] erro ao listar: {exc}")
                continue

            for entry in entries:
                try:
                    article = fetcher.fetch_article(source, entry)
                    if not article.text or len(article.text) < 180:
                        continue

                    content_hash = build_hash_from_article(article.url, article.title, article.text)
                    raw_article, _ = MateriaBruta.objects.update_or_create(
                        url_original=article.url,
                        defaults={
                            "fonte": source,
                            "titulo_extraido": article.title[:300],
                            "html_bruto": article.html,
                            "texto_base": article.text,
                            "hash_conteudo": content_hash,
                            "imagem_url": article.image_url,
                            "data_publicacao_original": article.published_at,
                            "metadata_json": article.metadata,
                        },
                    )

                    existing = NoticiaPublicada.objects.filter(materia_bruta=raw_article, status="published").first()
                    if existing:
                        processed += 1
                        continue

                    draft = build_news_draft(
                        source.nome,
                        {
                            "url_original": article.url,
                            "titulo_extraido": article.title,
                            "resumo_base": article.summary,
                            "texto_base": article.text,
                            "imagem_url": article.image_url,
                            "data_publicacao_original": article.published_at.isoformat() if article.published_at else "",
                            "categoria_padrao": source.categoria_padrao,
                            "outbound_links": article.metadata.get("outbound_links", []) if article.metadata else [],
                        },
                    )

                    status = resolve_status_for_draft(draft.confianca, Decimal(str(source.confianca_minima)))
                    story_fingerprint = build_story_fingerprint(
                        draft.titulo,
                        draft.resumo,
                        draft.categoria,
                        draft.topico,
                        article.text,
                    )
                    duplicate = find_duplicate_news(
                        draft.titulo,
                        draft.resumo,
                        draft.categoria,
                        draft.topico,
                        body=article.text,
                        outbound_urls=[
                            item.get("url", "")
                            for item in (article.metadata or {}).get("outbound_links", [])
                            if isinstance(item, dict)
                        ],
                    )

                    if duplicate and duplicate.materia_bruta_id != raw_article.pk:
                        processed += 1
                        continue

                    image_storage_path, illustrative = ensure_cover_for_news(draft)

                    with transaction.atomic():
                        noticia, created = NoticiaPublicada.objects.update_or_create(
                            materia_bruta=raw_article,
                            defaults={
                                "fonte": source,
                                "titulo": draft.titulo[:220],
                                "resumo": draft.resumo,
                                "conteudo": draft.conteudo,
                                "categoria": draft.categoria[:80],
                                "topico": draft.topico[:120],
                                "tags_json": draft.tags,
                                "url_fonte": article.url,
                                "status": status,
                                "confianca": draft.confianca,
                                "publicada_em": article.published_at or timezone.now(),
                                "imagem_url": draft.imagem_url,
                                "imagem_ilustrativa": illustrative,
                                "metadata_json": append_source_reference(
                                    {**(draft.metadata or {}), "story_fingerprint": story_fingerprint},
                                    source_name=source.nome,
                                    article_url=article.url,
                                    title=article.title,
                                ),
                            },
                        )
                        if image_storage_path:
                            noticia.imagem.name = image_storage_path
                            noticia.save(update_fields=["imagem"])
                        raw_article.processada_em = timezone.now()
                        raw_article.save(update_fields=["processada_em"])

                    processed += 1
                    if status == "published":
                        published += 1
                        if on_published:
                            try:
                                on_published(noticia)
                            except Exception:
                                pass

                except Exception as exc:
                    errors.append(f"[{source.nome}] erro: {exc}")

        job.status = "partial" if errors and published else ("failed" if errors else "success")
        job.quantidade_processada = processed
        job.quantidade_publicada = published
        job.erro = "\n".join(errors[:10])
        job.finalizado_em = timezone.now()
        job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "erro", "finalizado_em"])

    except Exception:
        job.status = "failed"
        job.finalizado_em = timezone.now()
        job.erro = traceback.format_exc()
        job.save(update_fields=["status", "finalizado_em", "erro"])

    return processed, published, errors


DEFAULT_SOURCES = [
    {
        "nome": "Passageiro de Primeira",
        "url": "https://passageirodeprimeira.com/",
        "ativa": True,
        "tipo_coleta": "html",
        "categoria_padrao": "Milhas e Pontos",
        "parser_key": "passageirodeprimeira",
    },
    {
        "nome": "Passageiro de Primeira RSS",
        "url": "https://passageirodeprimeira.com/feed/",
        "ativa": True,
        "tipo_coleta": "rss",
        "categoria_padrao": "Milhas e Pontos",
        "parser_key": "rss",
    },
    {
        "nome": "Melhores Cartoes",
        "url": "https://www.melhorescartoes.com.br/",
        "ativa": True,
        "tipo_coleta": "html",
        "categoria_padrao": "Cartões de Crédito",
        "parser_key": "melhorescartoes",
    },
    {
        "nome": "Melhores Cartoes RSS",
        "url": "https://www.melhorescartoes.com.br/feed/",
        "ativa": True,
        "tipo_coleta": "rss",
        "categoria_padrao": "Cartões de Crédito",
        "parser_key": "rss",
    },
]


def _ensure_default_sources():
    for source_data in DEFAULT_SOURCES:
        source, created = Fonte.objects.get_or_create(nome=source_data["nome"], defaults=source_data)
        if not created:
            updated = False
            for field in ("url", "tipo_coleta", "categoria_padrao", "parser_key", "ativa"):
                value = source_data.get(field)
                if value is not None and getattr(source, field) != value:
                    setattr(source, field, value)
                    updated = True
            if updated:
                source.save(update_fields=["url", "tipo_coleta", "categoria_padrao", "parser_key", "ativa", "atualizada_em"])


def _normalize_host(value: str) -> str:
    host = (urlparse(value).netloc or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _resolve_source_for_article_url(article_url: str) -> Fonte:
    _ensure_default_sources()
    article_host = _normalize_host(article_url)
    if not article_host:
        raise ValueError("URL da noticia invalida.")

    candidates = []
    for source in Fonte.objects.all():
        source_host = _normalize_host(source.url)
        if not source_host:
            continue
        if article_host == source_host or article_host.endswith(f".{source_host}") or source_host.endswith(f".{article_host}"):
            candidates.append(source)

    if candidates:
        candidates.sort(
            key=lambda source: (
                1 if source.tipo_coleta == "rss" or (source.parser_key or "").strip().lower() in {"rss", "feed"} else 0,
                0 if source.ativa else 1,
                len(_normalize_host(source.url)),
                source.nome.lower(),
            )
        )
        return candidates[0]

    parsed = urlparse(article_url)
    base_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/"
    existing = Fonte.objects.filter(url=base_url).order_by("id").first()
    if existing:
        return existing

    base_name = f"Manual {article_host}"
    source_name = base_name
    suffix = 2
    while Fonte.objects.filter(nome=source_name).exists():
        source_name = f"{base_name} {suffix}"
        suffix += 1

    return Fonte.objects.create(
        nome=source_name,
        url=base_url,
        ativa=False,
        tipo_coleta="html",
        categoria_padrao="Milhas e Pontos",
        parser_key="",
    )


def _resolve_manual_text_source(source_name: str = "Telegram Manual") -> Fonte:
    source, _ = Fonte.objects.get_or_create(
        nome=source_name,
        defaults={
            "url": "https://ncfly.com.br/telegram/manual/",
            "ativa": False,
            "tipo_coleta": "html",
            "categoria_padrao": "Promocoes",
            "parser_key": "",
        },
    )
    return source


_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_PERCENT_OFF_RE = re.compile(r"(\d{1,2})%\s*OFF", re.IGNORECASE)
_PROMO_CODE_RE = re.compile(r"\b([A-Z0-9]{4,20})\s*\|\s*(\d{1,2})%\s*OFF", re.IGNORECASE)
_PROMO_CODE_FALLBACK_RE = re.compile(r"\b([A-Z0-9]{4,20})\b(?:\s+com)?\s+(\d{1,2})%\s*OFF", re.IGNORECASE)
_DATE_VENDA_RE = re.compile(r"Data de venda:\s*([0-9/]+)\s*[Aa]\s*([0-9/]+)", re.IGNORECASE)
_DATE_VIAGEM_RE = re.compile(r"Data de viagem:\s*([0-9/]+)\s*[Aa]\s*([0-9/]+)", re.IGNORECASE)
_TIPO_PRODUTO_RE = re.compile(r"Tipo de produto:\s*(.+)", re.IGNORECASE)


def _build_manual_text_fallback_draft(raw_text: str, raw_article: dict) -> NewsDraft:
    clean_text = " ".join((raw_text or "").split()).strip()
    lowered = clean_text.lower()
    promo_match = _PROMO_CODE_RE.search(clean_text) or _PROMO_CODE_FALLBACK_RE.search(clean_text)
    percent_match = _PERCENT_OFF_RE.search(clean_text)
    sale_match = _DATE_VENDA_RE.search(clean_text)
    travel_match = _DATE_VIAGEM_RE.search(clean_text)
    product_match = _TIPO_PRODUTO_RE.search(clean_text)
    explicit_url = _URL_RE.search(clean_text)

    brand = _extract_cover_brand_label(
        clean_text,
        raw_article.get("titulo_extraido") or "",
        raw_article.get("resumo_base") or "",
        raw_article.get("categoria_padrao") or "",
    ) or ("Azul Viagens" if "azul viagens" in lowered else "NC Fly")
    code = promo_match.group(1).upper() if promo_match else ""
    percent = f"{promo_match.group(2)}% OFF" if promo_match else (f"{percent_match.group(1)}% OFF" if percent_match else "")
    sale_range = f"{sale_match.group(1)} a {sale_match.group(2)}" if sale_match else ""
    travel_range = f"{travel_match.group(1)} a {travel_match.group(2)}" if travel_match else ""
    product_type = product_match.group(1).strip(" .") if product_match else "pacotes de viagem"

    title_parts = [brand, "libera"]
    if code:
        title_parts.append(f"cupom {code}")
    else:
        title_parts.append("promocao especial")
    if percent:
        title_parts.append(f"com {percent}")
    if "pacote" in lowered:
        title_parts.append("em pacotes")
    title = " ".join(title_parts)

    summary_parts = []
    if percent:
        summary_parts.append(f"A campanha da {brand} aplica {percent}")
    else:
        summary_parts.append(f"A campanha da {brand} traz uma nova condicao promocional")
    if code:
        summary_parts.append(f"com o codigo {code}")
    if sale_range:
        summary_parts.append(f"para compras entre {sale_range}")
    if travel_range:
        summary_parts.append(f"e viagens de {travel_range}")
    summary = ", ".join(summary_parts).strip().rstrip(",") + "."

    paragraphs = []
    lead = f"{brand} colocou no ar uma nova campanha promocional"
    if code:
        lead += f" com o codigo {code}"
    if percent:
        lead += f", que entrega {percent}"
    if "pacote" in lowered:
        lead += " em pacotes"
    lead += "."
    paragraphs.append(lead)

    details = f"A promocao vale para {product_type}"
    if sale_range:
        details += f", com periodo de venda entre {sale_range}"
    if travel_range:
        details += f" e janela de viagem de {travel_range}"
    details += "."
    paragraphs.append(details)

    paragraphs.append(
        "Pelo regulamento enviado, a oferta esta sujeita a disponibilidade, pode ser encerrada sem aviso previo e nao se aplica a produtos fora das combinacoes elegiveis da campanha."
    )
    paragraphs.append(
        "Antes de concluir a compra, vale conferir as regras completas, canais participantes e possiveis restricoes operacionais informadas pela empresa."
    )

    cta_url = explicit_url.group(0).rstrip(").,;>") if explicit_url else ""
    cta_label = "Ver regras da promocao" if cta_url else ""

    draft = NewsDraft(
        titulo=title[:220],
        resumo=summary[:280],
        conteudo="\n\n".join(paragraphs),
        categoria="Promocoes",
        topico="Ofertas Relampago",
        tags=[item for item in [brand, code, "Promocoes"] if item],
        cta_url=cta_url,
        cta_label=cta_label,
        slug="",
        confianca=Decimal("0.62"),
        seo_title=title[:220],
        meta_description=summary[:160],
        imagem_url="",
        metadata={
            "provider": "manual_text_fallback",
            "raw_excerpt": clean_text[:500],
        },
    )
    return _apply_quality_rules(draft, raw_article)


def _should_prefer_manual_text_fallback(raw_text: str) -> bool:
    lowered = (raw_text or "").lower()
    score = 0
    if "tipo de produto:" in lowered:
        score += 1
    if "data de venda:" in lowered:
        score += 1
    if "data de viagem:" in lowered:
        score += 1
    if "regra jurídica:" in lowered or "regra juridica:" in lowered:
        score += 1
    if "promocode" in lowered or _PROMO_CODE_RE.search(raw_text or "") or _PROMO_CODE_FALLBACK_RE.search(raw_text or ""):
        score += 1
    return score >= 3


def _upsert_news_from_article(
    source: Fonte,
    article,
    *,
    publish_drafts: bool,
    refresh_published: bool,
    manual_submission: bool,
    draft_override: NewsDraft | None = None,
    allow_ai_cover: bool = True,
):
    if not article.text or len(article.text) < 180:
        raise ValueError("Texto insuficiente para gerar noticia.")

    content_hash = build_hash_from_article(article.url, article.title, article.text)
    raw_article, _ = MateriaBruta.objects.update_or_create(
        url_original=article.url,
        defaults={
            "fonte": source,
            "titulo_extraido": (article.title or "")[:300],
            "html_bruto": article.html,
            "texto_base": article.text,
            "hash_conteudo": content_hash,
            "imagem_url": article.image_url,
            "data_publicacao_original": article.published_at,
            "metadata_json": article.metadata,
        },
    )

    existing_news = NoticiaPublicada.objects.filter(materia_bruta=raw_article).first()
    if existing_news and existing_news.status == "published" and not refresh_published:
        return {
            "outcome": "already_published",
            "noticia": existing_news,
            "source": source,
            "processed": 1,
            "published": 1,
        }

    raw_article_payload = {
        "url_original": article.url,
        "titulo_extraido": article.title,
        "resumo_base": article.summary,
        "texto_base": article.text,
        "imagem_url": article.image_url,
        "data_publicacao_original": article.published_at.isoformat() if article.published_at else "",
        "categoria_padrao": source.categoria_padrao,
        "outbound_links": article.metadata.get("outbound_links", []) if article.metadata else [],
    }
    draft = draft_override or build_news_draft(source.nome, raw_article_payload)

    status = "published" if publish_drafts else resolve_status_for_draft(
        draft.confianca,
        Decimal(str(source.confianca_minima)),
    )

    story_fingerprint = build_story_fingerprint(
        draft.titulo,
        draft.resumo,
        draft.categoria,
        draft.topico,
        article.text,
    )
    duplicate_news = find_duplicate_news(
        draft.titulo,
        draft.resumo,
        draft.categoria,
        draft.topico,
        body=article.text,
        outbound_urls=[
            item.get("url", "")
            for item in (article.metadata or {}).get("outbound_links", [])
            if isinstance(item, dict)
        ],
        exclude_pk=existing_news.pk if existing_news else None,
    )

    if duplicate_news and duplicate_news.materia_bruta_id != raw_article.pk:
        duplicate_metadata = append_source_reference(
            duplicate_news.metadata_json,
            source_name=source.nome,
            article_url=article.url,
            title=article.title,
        )
        duplicate_metadata["story_fingerprint"] = story_fingerprint
        if manual_submission:
            duplicate_metadata["manual_submission"] = True
        duplicate_news.metadata_json = duplicate_metadata
        if not duplicate_news.imagem_url and draft.imagem_url:
            duplicate_news.imagem_url = draft.imagem_url
        duplicate_news.save(update_fields=["metadata_json", "imagem_url", "atualizada_em"])

        raw_metadata = dict(raw_article.metadata_json or {})
        raw_metadata["duplicate_of"] = {
            "slug": duplicate_news.slug,
            "title": duplicate_news.titulo,
            "url": duplicate_news.get_absolute_url(),
        }
        raw_metadata["story_fingerprint"] = story_fingerprint
        if manual_submission:
            raw_metadata["manual_submission"] = True
        raw_article.metadata_json = raw_metadata
        raw_article.processada_em = timezone.now()
        raw_article.save(update_fields=["metadata_json", "processada_em"])

        return {
            "outcome": "duplicate_reference",
            "noticia": duplicate_news,
            "source": source,
            "processed": 1,
            "published": 0,
        }

    if allow_ai_cover:
        image_storage_path, illustrative = ensure_cover_for_news(draft)
        if image_storage_path:
            draft.imagem_url = ""
    else:
        if draft.imagem_url:
            image_storage_path, illustrative = None, False
        else:
            file_name = f"portal/noticias/generated/{timezone.now():%Y%m%d%H%M%S}_{draft.slug[:50]}.svg"
            image_storage_path = _save_generated_file(file_name, _render_svg_cover_for_draft(draft))
            illustrative = True

    if image_storage_path:
        cover_source = "local_fallback" if image_storage_path.lower().endswith(".svg") else "ai_generated"
    elif draft.imagem_url:
        cover_source = "source_image"
    else:
        cover_source = "no_image"

    metadata_json = {
        **(draft.metadata or {}),
        "story_fingerprint": story_fingerprint,
        "cover_source": cover_source,
    }
    if manual_submission:
        metadata_json["manual_submission"] = True

    with transaction.atomic():
        noticia, created = NoticiaPublicada.objects.update_or_create(
            materia_bruta=raw_article,
            defaults={
                "fonte": source,
                "titulo": draft.titulo[:220],
                "resumo": draft.resumo,
                "conteudo": draft.conteudo,
                "categoria": draft.categoria[:80],
                "topico": draft.topico[:120],
                "tags_json": draft.tags,
                "url_fonte": article.url,
                "status": status,
                "confianca": draft.confianca,
                "publicada_em": article.published_at or timezone.now(),
                "imagem_url": draft.imagem_url,
                "imagem_ilustrativa": illustrative,
                "metadata_json": append_source_reference(
                    metadata_json,
                    source_name=source.nome,
                    article_url=article.url,
                    title=article.title,
                ),
            },
        )
        # Conteudos manuais enviados pelo Telegram podem nascer com um titulo
        # generico em uma tentativa anterior; quando o titulo final melhorar,
        # regenera o slug para manter a URL alinhada com a noticia atual.
        desired_slug = slugify(draft.titulo)[:220]
        if manual_submission and desired_slug and noticia.slug != desired_slug:
            noticia.slug = desired_slug
        update_fields = []
        if image_storage_path:
            noticia.imagem.name = image_storage_path
            update_fields.append("imagem")
        elif noticia.imagem:
            noticia.imagem.delete(save=False)
            noticia.imagem = None
            update_fields.append("imagem")
        if manual_submission and desired_slug and noticia.slug == desired_slug:
            update_fields.append("slug")
        if update_fields:
            noticia.save(update_fields=update_fields)
        raw_article.processada_em = timezone.now()
        raw_article.save(update_fields=["processada_em"])

    if status == "published":
        outcome = "updated" if existing_news or not created else "published"
    else:
        outcome = "draft"

    return {
        "outcome": outcome,
        "noticia": noticia,
        "source": source,
        "processed": 1,
        "published": 1 if status == "published" else 0,
    }


def sync_news_from_url(article_url: str, *, publish_drafts: bool = True, refresh_published: bool = True):
    job = JobExecucao.objects.create(
        job_name="sync_home_news_single_url",
        status="running",
        horario=timezone.now(),
    )
    try:
        source = _resolve_source_for_article_url(article_url)
        fetcher = get_fetcher_for_source(source)
        article = fetcher.fetch_article(source, FetchedEntry(url=article_url))
        result = _upsert_news_from_article(
            source,
            article,
            publish_drafts=publish_drafts,
            refresh_published=refresh_published,
            manual_submission=True,
        )
        job.status = "success"
        job.quantidade_processada = result["processed"]
        job.quantidade_publicada = result["published"]
        job.finalizado_em = timezone.now()
        job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "finalizado_em"])
        return result
    except Exception as exc:
        job.status = "failed"
        job.quantidade_processada = 0
        job.quantidade_publicada = 0
        job.finalizado_em = timezone.now()
        job.erro = str(exc)
        job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "finalizado_em", "erro"])
        raise


def sync_news_from_text(raw_text: str, *, source_name: str = "Telegram Manual", publish_drafts: bool = True):
    clean_text = (raw_text or "").strip()
    if len(clean_text) < 180:
        raise ValueError("Texto insuficiente para gerar noticia.")

    job = JobExecucao.objects.create(
        job_name="sync_home_news_single_text",
        status="running",
        horario=timezone.now(),
    )
    source = _resolve_manual_text_source(source_name)
    content_hash = hashlib.sha1(clean_text.encode("utf-8")).hexdigest()
    pseudo_url = f"https://ncfly.com.br/telegram/manual/{content_hash[:24]}/"
    article = FetchedEntry(
        url=pseudo_url,
        title="",
        summary="",
        html="",
        text=clean_text,
        metadata={
            "manual_submission": True,
            "submission_channel": "telegram",
        },
    )
    raw_article_payload = {
        "url_original": article.url,
        "titulo_extraido": "",
        "resumo_base": "",
        "texto_base": clean_text,
        "imagem_url": "",
        "data_publicacao_original": "",
        "categoria_padrao": "Promocoes",
        "outbound_links": article.metadata.get("outbound_links", []) if article.metadata else [],
    }

    try:
        if _should_prefer_manual_text_fallback(clean_text):
            fallback_draft = _build_manual_text_fallback_draft(clean_text, raw_article_payload)
            result = _upsert_news_from_article(
                source,
                article,
                publish_drafts=publish_drafts,
                refresh_published=True,
                manual_submission=True,
                draft_override=fallback_draft,
                allow_ai_cover=True,
            )
        else:
            result = _upsert_news_from_article(
                source,
                article,
                publish_drafts=publish_drafts,
                refresh_published=True,
                manual_submission=True,
            )
        job.status = "success"
        job.quantidade_processada = result["processed"]
        job.quantidade_publicada = result["published"]
        job.finalizado_em = timezone.now()
        job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "finalizado_em"])
        return result
    except Exception as exc:
        try:
            fallback_draft = _build_manual_text_fallback_draft(clean_text, raw_article_payload)
            result = _upsert_news_from_article(
                source,
                article,
                publish_drafts=publish_drafts,
                refresh_published=True,
                manual_submission=True,
                draft_override=fallback_draft,
                allow_ai_cover=True,
            )
            noticia = result.get("noticia")
            if noticia:
                metadata = dict(noticia.metadata_json or {})
                metadata["manual_text_primary_error"] = str(exc)
                noticia.metadata_json = metadata
                noticia.save(update_fields=["metadata_json", "atualizada_em"])
            job.status = "success"
            job.quantidade_processada = result["processed"]
            job.quantidade_publicada = result["published"]
            job.finalizado_em = timezone.now()
            job.erro = f"fallback_local: {exc}"
            job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "finalizado_em", "erro"])
            return result
        except Exception:
            job.status = "failed"
            job.quantidade_processada = 0
            job.quantidade_publicada = 0
            job.finalizado_em = timezone.now()
            job.erro = str(exc)
            job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "finalizado_em", "erro"])
            raise
