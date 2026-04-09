from django.core.management.base import BaseCommand

from portal.models import NoticiaPublicada
from portal.services.ai_pipeline import NewsDraft, _apply_quality_rules
from portal.services.deduplication import append_source_reference, build_story_fingerprint


class Command(BaseCommand):
    help = "Reclassifica noticias ja salvas, preenchendo categoria, topico e tags."

    def add_arguments(self, parser):
        parser.add_argument("--only-published", action="store_true", help="Processa apenas noticias publicadas.")

    def handle(self, *args, **options):
        queryset = NoticiaPublicada.objects.all().order_by("-publicada_em")
        if options["only_published"]:
            queryset = queryset.filter(status="published")

        updated = 0
        for noticia in queryset:
            draft = NewsDraft(
                titulo=noticia.titulo,
                resumo=noticia.resumo,
                conteudo=noticia.conteudo,
                categoria=noticia.categoria,
                topico=noticia.topico,
                tags=noticia.tags_json or [],
                cta_url=(noticia.metadata_json or {}).get("offer_cta", {}).get("url", ""),
                cta_label=(noticia.metadata_json or {}).get("offer_cta", {}).get("label", ""),
                slug=noticia.slug,
                confianca=noticia.confianca,
                imagem_url=noticia.imagem_url,
                metadata=noticia.metadata_json or {},
            )
            normalized = _apply_quality_rules(
                draft,
                {
                    "titulo_extraido": noticia.titulo,
                    "resumo_base": noticia.resumo,
                    "texto_base": noticia.conteudo,
                    "categoria_padrao": noticia.categoria,
                },
            )
            noticia.categoria = normalized.categoria
            noticia.topico = normalized.topico
            noticia.tags_json = normalized.tags
            metadata = dict(normalized.metadata or {})
            metadata["story_fingerprint"] = build_story_fingerprint(
                normalized.titulo,
                normalized.resumo,
                normalized.categoria,
                normalized.topico,
                noticia.materia_bruta.texto_base if noticia.materia_bruta_id and noticia.materia_bruta else noticia.conteudo,
            )
            noticia.metadata_json = append_source_reference(
                metadata,
                source_name=noticia.fonte.nome if noticia.fonte else "Fonte original",
                article_url=noticia.url_fonte,
                title=noticia.titulo,
            )
            noticia.save(update_fields=["categoria", "topico", "tags_json", "metadata_json", "atualizada_em"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Noticias reclassificadas: {updated}"))
