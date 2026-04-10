from django.core.management.base import BaseCommand, CommandError

from portal.models import NoticiaPublicada
from portal.services.ai_pipeline import NewsDraft, ensure_cover_for_news


class Command(BaseCommand):
    help = "Regenera a capa de uma noticia publicada a partir do slug."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Slug da noticia publicada.")
        parser.add_argument(
            "--keep-source-image",
            action="store_true",
            help="Mantem a imagem_url atual como referencia durante a geracao.",
        )
        parser.add_argument(
            "--clear-image-url",
            action="store_true",
            help="Limpa a imagem_url depois de salvar a nova capa local.",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        try:
            noticia = NoticiaPublicada.objects.get(slug=slug)
        except NoticiaPublicada.DoesNotExist as exc:
            raise CommandError(f"Noticia com slug '{slug}' nao encontrada.") from exc

        metadata = dict(noticia.metadata_json or {})
        cta = dict(metadata.get("offer_cta") or {})
        draft = NewsDraft(
            titulo=noticia.titulo,
            resumo=noticia.resumo,
            conteudo=noticia.conteudo,
            categoria=noticia.categoria,
            topico=noticia.topico,
            tags=list(noticia.tags_json or []),
            cta_url=cta.get("url", ""),
            cta_label=cta.get("label", ""),
            slug=noticia.slug,
            confianca=noticia.confianca,
            imagem_url=noticia.imagem_url if options["keep_source_image"] else "",
            metadata=metadata,
        )

        storage_path, illustrative = ensure_cover_for_news(draft)
        if not storage_path:
            message = (
                "Nenhuma nova capa foi gerada. "
                "Rode sem --keep-source-image para forcar uma capa local/IA."
                if options["keep_source_image"]
                else "Nenhuma nova capa foi gerada para essa noticia."
            )
            raise CommandError(message)

        cover_source = "local_fallback" if storage_path.lower().endswith(".svg") else "ai_generated"
        metadata["cover_source"] = cover_source

        noticia.imagem.name = storage_path
        noticia.imagem_ilustrativa = illustrative
        noticia.metadata_json = metadata

        update_fields = ["imagem", "imagem_ilustrativa", "metadata_json", "atualizada_em"]
        if options["clear_image_url"]:
            noticia.imagem_url = ""
            update_fields.append("imagem_url")

        noticia.save(update_fields=update_fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"Capa regenerada com sucesso. slug={noticia.slug} cover_source={cover_source} path={storage_path}"
            )
        )
