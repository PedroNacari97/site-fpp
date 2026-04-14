"""
Comando: republish_instagram

Regenera imagens e publica no Instagram as notícias de uma data específica.

Uso:
  python manage.py republish_instagram
  python manage.py republish_instagram --date 2026-04-12
  python manage.py republish_instagram --date 2026-04-12 --skip-image
  python manage.py republish_instagram --date 2026-04-12 --dry-run
  python manage.py republish_instagram --date 2026-04-12 --force
"""

import os
from datetime import date

from django.core.management.base import BaseCommand

from portal.models import NoticiaPublicada
from portal.services.ai_pipeline import NewsDraft, ensure_cover_for_news


class Command(BaseCommand):
    help = "Regenera imagens e publica no Instagram notícias de uma data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default="2026-04-12",
            help="Data de publicação no formato YYYY-MM-DD (padrão: 2026-04-12).",
        )
        parser.add_argument(
            "--skip-image",
            action="store_true",
            help="Não regenera imagem — publica no Instagram com a imagem atual.",
        )
        parser.add_argument(
            "--skip-instagram",
            action="store_true",
            help="Apenas regenera imagens, sem publicar no Instagram.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Publica no Instagram mesmo que já exista um evento publicado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista o que seria feito sem executar nada.",
        )

    def handle(self, *args, **options):
        target_date_str = options["date"]
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            self.stderr.write(self.style.ERROR(f"Data inválida: {target_date_str}. Use YYYY-MM-DD."))
            return

        skip_image = options["skip_image"]
        skip_instagram = options["skip_instagram"]
        force = options["force"]
        dry_run = options["dry_run"]

        noticias = (
            NoticiaPublicada.objects
            .filter(status="published", publicada_em__date=target_date)
            .order_by("publicada_em")
        )

        total = noticias.count()
        if total == 0:
            self.stdout.write(
                self.style.WARNING(f"Nenhuma notícia publicada encontrada em {target_date_str}.")
            )
            return

        self.stdout.write(
            self.style.HTTP_INFO(
                f"{'[DRY-RUN] ' if dry_run else ''}"
                f"Encontradas {total} notícia(s) publicadas em {target_date_str}."
            )
        )

        if dry_run:
            for n in noticias:
                ja_no_ig = n.instagram_eventos.filter(status="publicado").exists()
                self.stdout.write(
                    f"  • [{n.pk}] {n.titulo[:70]}"
                    f"{'  ⚠ já no Instagram' if ja_no_ig else ''}"
                )
            self.stdout.write(
                f"\nAções que seriam executadas:\n"
                f"  {'✓' if not skip_image else '✗'} Regenerar imagem\n"
                f"  {'✓' if not skip_instagram else '✗'} Publicar no Instagram"
                f"{'  (force)' if force else ''}"
            )
            return

        ok_image = 0
        ok_instagram = 0
        err_image = 0
        err_instagram = 0

        for index, noticia in enumerate(noticias, start=1):
            prefix = f"[{index}/{total}] {noticia.titulo[:60]}"
            self.stdout.write(f"\n{prefix}")

            # ── Regenerar imagem ──────────────────────────────────────────
            if not skip_image:
                self.stdout.write("  → Regenerando imagem...")
                try:
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
                        imagem_url="",  # força geração original — não usa imagem de terceiro
                        imagem_prompt=metadata.get("imagem_prompt", ""),
                        metadata=metadata,
                    )

                    storage_path, illustrative = ensure_cover_for_news(draft)

                    if storage_path:
                        cover_type = "SVG" if storage_path.endswith(".svg") else "IA"
                        metadata["cover_source"] = (
                            "local_fallback" if storage_path.endswith(".svg") else "ai_generated"
                        )
                        noticia.imagem.name = storage_path
                        noticia.imagem_url = ""
                        noticia.imagem_ilustrativa = illustrative
                        noticia.metadata_json = metadata
                        noticia.save(update_fields=[
                            "imagem", "imagem_url", "imagem_ilustrativa",
                            "metadata_json", "atualizada_em",
                        ])
                        ok_image += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Imagem {cover_type} salva: {storage_path}")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING("  ⚠ Nenhuma imagem nova gerada (imagem de fonte mantida).")
                        )
                        ok_image += 1

                except Exception as exc:
                    err_image += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ Erro na imagem: {exc}"))

            # ── Publicar no Instagram ─────────────────────────────────────
            if not skip_instagram:
                from gestao.services.instagram_publisher import (
                    is_instagram_configured,
                    publish_noticia_to_instagram,
                )
                from gestao.models.instagram_noticia_evento import InstagramNoticiaEvento

                if not is_instagram_configured():
                    self.stdout.write(
                        self.style.ERROR(
                            "  ✗ Instagram não configurado. "
                            "Defina INSTAGRAM_ACCESS_TOKEN no Railway."
                        )
                    )
                    break

                ja_publicado = noticia.instagram_eventos.filter(
                    status=InstagramNoticiaEvento.STATUS_PUBLICADO
                ).exists()

                if ja_publicado and not force:
                    self.stdout.write(
                        self.style.WARNING("  ⚠ Já publicado no Instagram. Use --force para republicar.")
                    )
                    continue

                if ja_publicado and force:
                    self.stdout.write("  → Forçando republicação no Instagram...")
                else:
                    self.stdout.write("  → Publicando no Instagram...")

                try:
                    # --force: remove evento publicado anterior para não cair na verificação de idempotência
                    if ja_publicado and force:
                        noticia.instagram_eventos.filter(
                            status=InstagramNoticiaEvento.STATUS_PUBLICADO
                        ).delete()

                    publish_noticia_to_instagram(noticia)

                    # Verificar se foi publicado com sucesso
                    evento = noticia.instagram_eventos.filter(
                        status=InstagramNoticiaEvento.STATUS_PUBLICADO
                    ).order_by("-criado_em").first()

                    if evento:
                        ok_instagram += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Instagram: post_id={evento.ig_post_id}")
                        )
                    else:
                        # Verificar se teve erro
                        evento_erro = noticia.instagram_eventos.filter(
                            status=InstagramNoticiaEvento.STATUS_ERRO
                        ).order_by("-criado_em").first()
                        err_instagram += 1
                        erro_msg = evento_erro.erro[:120] if evento_erro else "erro desconhecido"
                        self.stdout.write(self.style.ERROR(f"  ✗ Instagram falhou: {erro_msg}"))

                except Exception as exc:
                    err_instagram += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ Erro no Instagram: {exc}"))

        # ── Resumo ───────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(self.style.HTTP_INFO("RESUMO"))
        if not skip_image:
            self.stdout.write(f"  Imagens:   {ok_image} ok  |  {err_image} erro(s)")
        if not skip_instagram:
            self.stdout.write(f"  Instagram: {ok_instagram} ok  |  {err_instagram} erro(s)")
        self.stdout.write("─" * 60)
