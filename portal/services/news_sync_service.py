from __future__ import annotations
import traceback
from datetime import timedelta
from django.utils import timezone
from portal.models import Fonte, JobExecucao, MateriaBruta, NoticiaPublicada
from portal.services.ai_pipeline import (
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
from portal.services.fetchers.registry import get_fetcher_for_source
from decimal import Decimal
from django.db import transaction


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

    # URLs que já têm notícia publicada — filtrar antes de processar
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
                # Busca candidatos e filtra URLs já publicadas antes de fatiar pelo limit
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
                    story_fingerprint = build_story_fingerprint(draft.titulo, draft.resumo, draft.categoria, draft.topico)
                    duplicate = find_duplicate_news(draft.titulo, draft.resumo, draft.categoria, draft.topico)

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
