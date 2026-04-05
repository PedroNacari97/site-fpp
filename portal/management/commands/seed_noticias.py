"""
Importa as notícias e fontes do seed fixture para o banco de dados.
Só insere registros que ainda não existem (por pk/slug).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = "Importa fontes e notícias do fixture local para o banco de dados"

    def handle(self, *args, **options):
        base = Path(__file__).resolve().parents[3] / "portal" / "fixtures"

        # 1. Importar Fontes
        from portal.models import Fonte
        fontes_path = base / "fontes_seed.json"
        if fontes_path.exists():
            data = json.loads(fontes_path.read_text(encoding="utf-8"))
            created = 0
            for item in data:
                pk = item["pk"]
                fields = item["fields"]
                _, was_created = Fonte.objects.get_or_create(
                    pk=pk,
                    defaults={
                        "nome": fields.get("nome", ""),
                        "url": fields.get("url", ""),
                        "ativa": fields.get("ativa", True),
                        "tipo_coleta": fields.get("tipo_coleta", "rss"),
                        "categoria_padrao": fields.get("categoria_padrao", ""),
                        "parser_key": fields.get("parser_key", ""),
                    },
                )
                if was_created:
                    created += 1
            self.stdout.write(f"Fontes: {created} criadas, {len(data) - created} já existiam")
        else:
            self.stderr.write("Arquivo fontes_seed.json não encontrado")
            return

        # 2. Importar Notícias
        from portal.models import NoticiaPublicada
        noticias_path = base / "noticias_seed.json"
        if not noticias_path.exists():
            self.stderr.write("Arquivo noticias_seed.json não encontrado")
            return

        data = json.loads(noticias_path.read_text(encoding="utf-8"))
        created = 0
        skipped = 0
        for item in data:
            pk = item["pk"]
            fields = item["fields"]

            if NoticiaPublicada.objects.filter(pk=pk).exists():
                skipped += 1
                continue
            if NoticiaPublicada.objects.filter(slug=fields.get("slug", "")).exists():
                skipped += 1
                continue

            fonte_id = fields.get("fonte")
            fonte = None
            if fonte_id:
                try:
                    fonte = Fonte.objects.get(pk=fonte_id)
                except Fonte.DoesNotExist:
                    pass

            try:
                NoticiaPublicada.objects.create(
                    pk=pk,
                    titulo=fields.get("titulo", ""),
                    resumo=fields.get("resumo", ""),
                    conteudo=fields.get("conteudo", ""),
                    slug=fields.get("slug", ""),
                    categoria=fields.get("categoria", ""),
                    topico=fields.get("topico", ""),
                    tags_json=fields.get("tags_json", "[]"),
                    imagem=fields.get("imagem", "") or "",
                    imagem_url=fields.get("imagem_url", ""),
                    imagem_ilustrativa=fields.get("imagem_ilustrativa", False),
                    url_fonte=fields.get("url_fonte", ""),
                    status=fields.get("status", "published"),
                    confianca=fields.get("confianca") or None,
                    publicada_em=parse_datetime(fields["publicada_em"]) if fields.get("publicada_em") else None,
                    metadata_json=fields.get("metadata_json", "{}"),
                    fonte=fonte,
                )
                created += 1
            except Exception as exc:
                self.stderr.write(f"Erro ao criar noticia pk={pk} slug={fields.get('slug','?')}: {exc}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Notícias: {created} importadas, {skipped} ignoradas (já existiam ou erro)"
            )
        )
