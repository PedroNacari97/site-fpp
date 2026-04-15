"""Importa o CSV ``marcas_api_brandfetch_v2.csv`` para ``MarcaCatalogo``.

Uso:
    python manage.py import_marcas_catalogo
    python manage.py import_marcas_catalogo --csv /path/para/arquivo.csv
    python manage.py import_marcas_catalogo --force  # sobrescreve tudo

O CSV é o seed (raiz do projeto); depois do import o ``brand_catalog.py``
consulta direto o banco.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from gestao.models import MarcaCatalogo


SUPPORTED_LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _keyword_from_brand(marca: str, dominio: str) -> list[str]:
    """Gera keywords default a partir do nome da marca e dominio."""
    kws: list[str] = []
    marca = (marca or "").strip()
    dominio = (dominio or "").strip().lower()
    if marca:
        kws.append(marca.lower())
    if dominio:
        root = dominio.split("/")[0].split(".")[0]
        if root and root not in {kw.replace(" ", "") for kw in kws}:
            kws.append(root)
    return [k for k in kws if k]


def _is_supported_logo(url: str) -> bool:
    if not url:
        return False
    lower = url.lower().split("?", 1)[0]
    return lower.endswith(SUPPORTED_LOGO_EXTS)


class Command(BaseCommand):
    help = "Importa o catalogo de marcas a partir do CSV Brandfetch para o banco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default=None,
            help="Caminho ou URL do CSV (default: marcas_api_brandfetch_v2.csv na raiz).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobrescreve cor/logo mesmo se o registro ja existir.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nao grava nada, apenas mostra o que seria feito.",
        )

    def _read_csv(self, source: str | None) -> bytes:
        if source and (source.startswith("http://") or source.startswith("https://")):
            req = Request(source, headers={"User-Agent": "NCfly/brand-catalog"})
            with urlopen(req, timeout=30) as resp:
                return resp.read()

        if source:
            path = Path(source)
        else:
            path = Path(__file__).resolve().parents[3] / "marcas_api_brandfetch_v2.csv"

        if not path.is_file():
            raise CommandError(f"CSV nao encontrado: {path}")
        return path.read_bytes()

    def handle(self, *args, **options):
        raw = self._read_csv(options.get("csv"))
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))

        created = updated = skipped = 0
        force = options["force"]
        dry_run = options["dry_run"]

        with transaction.atomic():
            for row in reader:
                marca = (row.get("marca") or "").strip()
                dominio = (row.get("dominio") or "").strip().lower()
                nicho = (row.get("nicho") or "").strip()
                cor_hex = (row.get("cor_hex") or "").strip() or "#000000"
                logo_url = (row.get("logo_url") or "").strip()

                if not marca:
                    skipped += 1
                    continue

                # Guarda URL so se for raster (OpenAI /images/edits nao aceita SVG).
                logo_final = logo_url if _is_supported_logo(logo_url) else ""
                keywords = _keyword_from_brand(marca, dominio)

                defaults = {
                    "nicho": nicho,
                    "dominio": dominio,
                    "cor_hex": cor_hex,
                    "logo_url": logo_final,
                    "keywords": keywords,
                    "ativo": True,
                }

                if dry_run:
                    exists = MarcaCatalogo.objects.filter(nome__iexact=marca).exists()
                    self.stdout.write(
                        f"[dry-run] {'update' if exists else 'create'}: {marca}"
                    )
                    if exists:
                        updated += 1
                    else:
                        created += 1
                    continue

                obj, was_created = MarcaCatalogo.objects.get_or_create(
                    nome=marca, defaults=defaults
                )
                if was_created:
                    created += 1
                    continue

                changed = False
                for field in ("nicho", "dominio"):
                    if not getattr(obj, field) and defaults[field]:
                        setattr(obj, field, defaults[field])
                        changed = True
                if force or obj.cor_hex in ("", "#000000"):
                    if obj.cor_hex != cor_hex:
                        obj.cor_hex = cor_hex
                        changed = True
                if force or not obj.logo_url:
                    if obj.logo_url != logo_final:
                        obj.logo_url = logo_final
                        changed = True
                if not obj.keywords and keywords:
                    obj.keywords = keywords
                    changed = True
                if changed:
                    obj.save()
                    updated += 1
                else:
                    skipped += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"OK criadas={created} atualizadas={updated} puladas={skipped} dry_run={dry_run}"
            )
        )
