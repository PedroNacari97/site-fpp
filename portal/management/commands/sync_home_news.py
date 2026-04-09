from __future__ import annotations

from decimal import Decimal
import traceback

from django.core.management.base import BaseCommand
from django.db import transaction
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


DEFAULT_SOURCES = [
    {
        "nome": "Passageiro de Primeira",
        "url": "https://passageirodeprimeira.com/",
        "ativa": False,
        "tipo_coleta": "html",
        "categoria_padrao": "Milhas",
        "parser_key": "passageirodeprimeira",
    },
    {
        "nome": "Melhores Cartoes",
        "url": "https://www.melhorescartoes.com.br/",
        "ativa": True,
        "tipo_coleta": "html",
        "categoria_padrao": "Cartoes",
        "parser_key": "melhorescartoes",
    },
]


class Command(BaseCommand):
    help = "Coleta, reescreve e publica noticias para a home publica."

    def add_arguments(self, parser):
        parser.add_argument("--source", dest="source_name", help="Nome de uma fonte especifica")
        parser.add_argument("--limit", type=int, default=20, help="Quantidade maxima de artigos por fonte apos a varredura completa")
        parser.add_argument("--publish-drafts", action="store_true", help="Publica tudo, ignorando confianca minima")
        parser.add_argument("--refresh-published", action="store_true", help="Reprocessa noticias ja publicadas")

    def handle(self, *args, **options):
        self._ensure_default_sources()
        job = JobExecucao.objects.create(job_name="sync_home_news", status="running", horario=timezone.now())
        processed = 0
        published = 0
        errors: list[str] = []

        queryset = Fonte.objects.filter(ativa=True)
        if options.get("source_name"):
            queryset = queryset.filter(nome__iexact=options["source_name"])

        try:
            for source in queryset:
                source_processed, source_published, source_errors = self._sync_source(
                    source,
                    limit=options["limit"],
                    publish_drafts=options["publish_drafts"],
                    refresh_published=options["refresh_published"],
                )
                processed += source_processed
                published += source_published
                errors.extend(source_errors)

            job.status = "partial" if errors and published else ("failed" if errors else "success")
            job.quantidade_processada = processed
            job.quantidade_publicada = published
            job.erro = "\n".join(errors[:20])
            job.finalizado_em = timezone.now()
            job.save(update_fields=["status", "quantidade_processada", "quantidade_publicada", "erro", "finalizado_em"])
        except Exception:
            job.status = "failed"
            job.finalizado_em = timezone.now()
            job.erro = traceback.format_exc()
            job.quantidade_processada = processed
            job.quantidade_publicada = published
            job.save(update_fields=["status", "finalizado_em", "erro", "quantidade_processada", "quantidade_publicada"])
            raise

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync concluido. Processadas: {processed} | Publicadas: {published} | Status job: {job.status}"
            )
        )

    def _ensure_default_sources(self):
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

    def _archive_known_non_article_items(self, source: Fonte) -> None:
        parser_key = (source.parser_key or "").strip().lower()
        if parser_key == "passageirodeprimeira":
            NoticiaPublicada.objects.filter(
                fonte=source,
                url_fonte__icontains="/categorias/",
                status="published",
            ).update(status="archived")

    def _sync_source(self, source: Fonte, *, limit: int, publish_drafts: bool, refresh_published: bool) -> tuple[int, int, list[str]]:
        processed = 0
        published = 0
        errors: list[str] = []
        self._archive_known_non_article_items(source)
        fetcher = get_fetcher_for_source(source)
        try:
            entries = fetcher.list_entries(source)[:limit]
        except Exception as exc:
            return 0, 0, [f"[{source.nome}] erro ao listar entradas: {exc}"]

        for entry in entries:
            try:
                article = fetcher.fetch_article(source, entry)
                if not article.text or len(article.text) < 180:
                    errors.append(f"[{source.nome}] texto insuficiente em {article.url}")
                    continue

                content_hash = build_hash_from_article(article.url, article.title, article.text)
                raw_defaults = {
                    "fonte": source,
                    "titulo_extraido": article.title[:300],
                    "html_bruto": article.html,
                    "texto_base": article.text,
                    "hash_conteudo": content_hash,
                    "imagem_url": article.image_url,
                    "data_publicacao_original": article.published_at,
                    "metadata_json": article.metadata,
                }
                raw_article, _ = MateriaBruta.objects.update_or_create(
                    url_original=article.url,
                    defaults=raw_defaults,
                )

                existing_news = NoticiaPublicada.objects.filter(materia_bruta=raw_article).first()
                if existing_news and existing_news.status == "published" and not refresh_published:
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
                    raw_article.metadata_json = raw_metadata
                    raw_article.processada_em = timezone.now()
                    raw_article.save(update_fields=["metadata_json", "processada_em"])
                    processed += 1
                    continue

                image_storage_path = None
                illustrative = False
                image_storage_path, illustrative = ensure_cover_for_news(draft)
                if image_storage_path:
                    cover_source = "local_fallback" if image_storage_path.lower().endswith(".svg") else "ai_generated"
                elif draft.imagem_url:
                    cover_source = "source_image"
                else:
                    cover_source = "no_image"

                with transaction.atomic():
                    defaults = {
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
                            {
                                **(draft.metadata or {}),
                                "story_fingerprint": story_fingerprint,
                                "cover_source": cover_source,
                            },
                            source_name=source.nome,
                            article_url=article.url,
                            title=article.title,
                        ),
                    }
                    noticia, _ = NoticiaPublicada.objects.update_or_create(
                        materia_bruta=raw_article,
                        defaults=defaults,
                    )
                    if image_storage_path:
                        noticia.imagem.name = image_storage_path
                        noticia.save(update_fields=["imagem"])
                    elif noticia.imagem:
                        noticia.imagem.delete(save=False)
                        noticia.imagem = None
                        noticia.save(update_fields=["imagem"])
                    raw_article.processada_em = timezone.now()
                    raw_article.save(update_fields=["processada_em"])

                processed += 1
                if status == "published":
                    published += 1
            except Exception as exc:
                errors.append(f"[{source.nome}] erro ao processar {entry.url}: {exc}")
        return processed, published, errors
