"""Marca como interrompidos os jobs de atualizacao em massa parados.

Roda no cron a cada minuto no Railway (ou manualmente):
    python manage.py purgar_jobs_orfaos
    python manage.py purgar_jobs_orfaos --timeout 5

Sem isso, um deploy/crash deixaria status='em_andamento' eternamente, segurando
o debounce e enganando a UI. O cleanup so altera registros antigos (> 10min por
default), entao e seguro rodar com frequencia.
"""
from django.core.management.base import BaseCommand

from gestao.services.monitoring.bulk_runner import (
    JOB_TIMEOUT_MINUTOS,
    marcar_jobs_orfaos,
)


class Command(BaseCommand):
    help = "Marca jobs de atualizacao em massa parados como interrompidos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=JOB_TIMEOUT_MINUTOS,
            help=f"Tempo (minutos) para considerar um job orfao. Default: {JOB_TIMEOUT_MINUTOS}.",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        marcados = marcar_jobs_orfaos(timeout_minutos=timeout)
        if marcados:
            self.stdout.write(
                self.style.WARNING(
                    f"{marcados} job(s) marcado(s) como interrompido (>{timeout}min)."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Nenhum job orfao."))
