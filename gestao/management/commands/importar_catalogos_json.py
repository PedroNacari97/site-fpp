import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from gestao.models import Aeroporto, CompanhiaAerea, ProgramaFidelidade


class Command(BaseCommand):
    help = "Importa aeroportos, programas de pontos e companhias aereas a partir de um JSON de catalogo."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str, help="Caminho para o arquivo JSON exportado.")

    def handle(self, *args, **options):
        arquivo = Path(options["arquivo"]).expanduser()
        if not arquivo.exists():
            raise CommandError(f"Arquivo nao encontrado: {arquivo}")

        try:
            payload = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON invalido: {exc}") from exc

        with transaction.atomic():
            aeroportos_stats = self._importar_aeroportos(payload.get("aeroportos", []))
            companhias_stats = self._importar_companhias(payload.get("companhias_aereas", []))
            programas_stats = self._importar_programas(payload.get("programas_fidelidade", []))

        self.stdout.write(
            self.style.SUCCESS(
                "Importacao concluida com sucesso.\n"
                f"Aeroportos: {aeroportos_stats['created']} criados, {aeroportos_stats['updated']} atualizados\n"
                f"Companhias: {companhias_stats['created']} criadas, {companhias_stats['updated']} atualizadas\n"
                f"Programas: {programas_stats['created']} criados, {programas_stats['updated']} atualizados"
            )
        )

    def _importar_aeroportos(self, aeroportos):
        stats = {"created": 0, "updated": 0}
        for item in aeroportos:
            sigla = str(item.get("sigla", "")).strip().upper()
            if not sigla:
                continue

            defaults = {
                "nome": str(item.get("nome", "")).strip(),
                "cidade": str(item.get("cidade", "")).strip(),
                "estado": str(item.get("estado", "")).strip(),
            }

            instance = Aeroporto.objects.filter(sigla=sigla).order_by("id").first()
            if instance:
                changed = False
                for field, value in defaults.items():
                    if getattr(instance, field) != value:
                        setattr(instance, field, value)
                        changed = True
                if changed:
                    instance.save(update_fields=["nome", "cidade", "estado"])
                    stats["updated"] += 1
            else:
                Aeroporto.objects.create(sigla=sigla, **defaults)
                stats["created"] += 1
        return stats

    def _importar_companhias(self, companhias):
        stats = {"created": 0, "updated": 0}
        for item in companhias:
            nome = str(item.get("nome", "")).strip()
            if not nome:
                continue

            site_url = str(item.get("site_url", "")).strip() or None
            instance = CompanhiaAerea.objects.filter(nome=nome).order_by("id").first()
            if instance:
                if instance.site_url != site_url:
                    instance.site_url = site_url
                    instance.save(update_fields=["site_url"])
                    stats["updated"] += 1
            else:
                CompanhiaAerea.objects.create(nome=nome, site_url=site_url)
                stats["created"] += 1
        return stats

    def _importar_programas(self, programas):
        stats = {"created": 0, "updated": 0}
        source_map = {}

        ordered = sorted(
            programas,
            key=lambda item: 0 if str(item.get("tipo", "")).strip() == ProgramaFidelidade.TIPO_PRINCIPAL else 1,
        )

        for item in ordered:
            nome = str(item.get("nome", "")).strip()
            if not nome:
                continue

            tipo = str(item.get("tipo", "")).strip() or ProgramaFidelidade.TIPO_PRINCIPAL
            base_source_id = item.get("programa_base_id")
            programa_base = source_map.get(base_source_id) if base_source_id else None

            defaults = {
                "descricao": str(item.get("descricao", "")).strip(),
                "tipo": tipo,
                "programa_base": programa_base,
                "preco_medio_milheiro": item.get("preco_medio_milheiro") or 0,
                "quantidade_cpfs_disponiveis": item.get("quantidade_cpfs_disponiveis"),
            }

            instance = ProgramaFidelidade.objects.filter(nome=nome).order_by("id").first()
            if instance:
                changed_fields = []
                for field, value in defaults.items():
                    current_value = getattr(instance, field)
                    current_id = getattr(current_value, "id", current_value)
                    new_id = getattr(value, "id", value)
                    if current_id != new_id:
                        setattr(instance, field, value)
                        changed_fields.append(field)
                if changed_fields:
                    instance.save(update_fields=changed_fields)
                    stats["updated"] += 1
            else:
                instance = ProgramaFidelidade.objects.create(**defaults, nome=nome)
                stats["created"] += 1

            source_id = item.get("id")
            if source_id is not None:
                source_map[source_id] = instance

        return stats
